"""
Spell Timer v0.1
Features:
- System Tray Icon (Uses custom .ico if available).
- Bundled Resource Support.
- Persistence.
- Graceful Exit.
"""

from __future__ import annotations
import os
import sys
import json
import signal
import ctypes
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple
import requests
import urllib3
from PIL import Image, ImageTk, ImageDraw, ImageOps
import pystray 

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- EXE RESOURCE HELPER ---
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# --- CONFIGURATION ---
class Config:
    if getattr(sys, 'frozen', False):
        APP_DIR = os.path.dirname(sys.executable)
    else:
        APP_DIR = os.path.dirname(os.path.abspath(__file__))
        
    CONFIG_FILE = os.path.join(APP_DIR, "config.json")

    # === SPELL TIMERS ===
    SPELL_TIMERS = {
        "summonerflash":    300,
        "summonerteleport": 360,
        "summonerheal":     240,
        "summonerboost":    210, # Cleanse
        "summonerexhaust":  210,
        "summonerhaste":    210, # Ghost
        "summonerbarrier":  180,
        "summonerdot":      180, # Ignite
        "summonersmite":    15,
        "summonersnowball": 80,  # ARAM Mark
        "summonerclarity":  240,
        "summonermana":     240
    }
    
    # === VISUALS ===
    GLOBAL_OPACITY = 0.85   
    ICON_SIZE = 38          
    ROW_PADDING_Y = 6       
    SHOW_SEPARATOR = True   
    
    COLOR_BG = "#091428"        
    COLOR_BORDER = "#463714"    
    COLOR_SEPARATOR = "#000000" 
    COLOR_TEXT_ACTIVE = "#FFFFFF" 
    COLOR_TEXT_OUTLINE = "#000000"
    
    COLOR_PINNED = "#8B0000"    
    COLOR_HANDLE = "#666666"    
    
    FONT_FAMILY = "Arial"     
    BASE_FONT_SIZE = 12         
    
    # API URLs
    LCL_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
    DDRAGON_VER_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
    DDRAGON_DATA_URL = "https://ddragon.leagueoflegends.com/cdn/{}/data/en_US/summoner.json"
    
    CHECK_INTERVAL = 3000

# --- WIN32 API ---
class Win32Utils:
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST = 0x00000008

    @staticmethod
    def set_no_focus(hwnd: int):
        try:
            style = ctypes.windll.user32.GetWindowLongW(hwnd, Win32Utils.GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, 
                Win32Utils.GWL_EXSTYLE, 
                style | Win32Utils.WS_EX_NOACTIVATE | Win32Utils.WS_EX_TOPMOST
            )
        except Exception:
            pass

# --- DDRAGON MANAGER ---
class DDragonManager:
    @staticmethod
    def update_timers():
        print("[DDragon] Checking for updates...")
        try:
            v_resp = requests.get(Config.DDRAGON_VER_URL, timeout=2)
            if v_resp.status_code != 200: return
            version = v_resp.json()[0]

            url = Config.DDRAGON_DATA_URL.format(version)
            d_resp = requests.get(url, timeout=3)
            if d_resp.status_code != 200: return
            
            data = d_resp.json().get("data", {})
            for spell_id, info in data.items():
                cooldowns = info.get("cooldown", [300])
                cd = int(cooldowns[0])
                key = spell_id.lower()
                Config.SPELL_TIMERS[key] = cd
        except Exception as e:
            print(f"[DDragon] Update failed: {e}")

# --- DATA MANAGER ---
class GameDataManager:
    @staticmethod
    def fetch_data() -> Optional[Dict]:
        try:
            resp = requests.get(Config.LCL_URL, verify=False, timeout=0.5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return None

    @staticmethod
    def parse_enemies(data: Dict) -> List[Dict]:
        if not data: return GameDataManager._get_dummy_data()
        
        my_team = data.get("activePlayer", {}).get("team", "ORDER")
        all_players = data.get("allPlayers") or []
        enemies = []

        for p in all_players:
            if p.get("team") == my_team: continue
            
            raw_name = p.get("rawChampionName", "") or p.get("championName", "")
            champ_name = raw_name.split("_")[-1] if "_" in raw_name else raw_name
            spells = p.get("summonerSpells", {})
            
            enemies.append({
                "champ": champ_name,
                "spell1": GameDataManager._clean_spell_name(spells.get("summonerSpellOne", {}).get("rawDisplayName")),
                "spell2": GameDataManager._clean_spell_name(spells.get("summonerSpellTwo", {}).get("rawDisplayName")),
            })
        return enemies

    @staticmethod
    def _clean_spell_name(raw: Optional[str]) -> str:
        if not raw: return "Unknown"
        raw_lower = raw.lower()
        if "teleport" in raw_lower: return "SummonerTeleport"
        if "smite" in raw_lower: return "SummonerSmite"
        if "flash" in raw_lower: return "SummonerFlash"
        if "ignite" in raw_lower or "dot" in raw_lower: return "SummonerDot"
        if "barrier" in raw_lower: return "SummonerBarrier"
        if "heal" in raw_lower: return "SummonerHeal"
        if "exhaust" in raw_lower: return "SummonerExhaust"
        if "cleanse" in raw_lower or "boost" in raw_lower: return "SummonerBoost"
        if "ghost" in raw_lower or "haste" in raw_lower: return "SummonerHaste"
        parts = raw.split("_")
        for p in reversed(parts):
            if p.startswith("Summoner") and p != "SummonerSpell": return p
        return "Unknown"

    @staticmethod
    def _get_dummy_data():
        return [
            {"champ": "Darius", "spell1": "SummonerFlash", "spell2": "SummonerTeleport"},
            {"champ": "LeeSin", "spell1": "SummonerFlash", "spell2": "SummonerSmite"},
        ]

# --- ASSET MANAGER ---
class AssetManager:
    @staticmethod
    def load_icon(folder: str, name: str, size: Tuple[int, int], is_round: bool = False) -> ImageTk.PhotoImage:
        path = resource_path(os.path.join("assets", folder, name + ".png"))
        try:
            img = Image.open(path).convert("RGBA")
        except FileNotFoundError:
            img = Image.new("RGBA", size, "#222")
            draw = ImageDraw.Draw(img)
            draw.rectangle([0,0, size[0]-1, size[1]-1], outline="#555")
            text = name[:2] if name else "??"
            draw.text((size[0]//2, size[1]//2), text, fill="#888", anchor="mm")

        img = img.resize(size, Image.Resampling.LANCZOS)
        if is_round:
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
            img.putalpha(mask)
        return ImageTk.PhotoImage(img)

    @staticmethod
    def create_dim_layer(size: Tuple[int, int]) -> ImageTk.PhotoImage:
        img = Image.new("RGBA", size, (0, 0, 0, 180)) 
        return ImageTk.PhotoImage(img)

# --- UI WIDGET ---
class SpellTimerWidget(tk.Canvas):
    def __init__(self, parent, spell_name: str):
        super().__init__(parent, width=Config.ICON_SIZE, height=Config.ICON_SIZE, 
                         bg=Config.COLOR_BG, highlightthickness=0)
        self.spell_name = spell_name
        self.is_active = False
        self.timer_job = None

        self.icon_img = AssetManager.load_icon("spells", spell_name, (Config.ICON_SIZE, Config.ICON_SIZE))
        self.create_image(0, 0, image=self.icon_img, anchor="nw")
        
        self.dim_img = AssetManager.create_dim_layer((Config.ICON_SIZE, Config.ICON_SIZE))
        self.dim_id = self.create_image(0, 0, image=self.dim_img, anchor="nw", state="hidden")
        self.text_id = self.create_text(Config.ICON_SIZE//2, Config.ICON_SIZE//2, text="", state="hidden")

        self.bind("<Button-1>", self._on_left_click)  
        self.bind("<Button-3>", self._on_right_click) 

    def _on_left_click(self, event):
        if self.is_active: return
        key = self.spell_name.lower()
        cd = Config.SPELL_TIMERS.get(key, 300)
        self._start_timer(cd)

    def _on_right_click(self, event):
        if self.is_active: self._reset()

    def _start_timer(self, duration):
        self.is_active = True
        self.itemconfig(self.dim_id, state="normal")
        self.itemconfig(self.text_id, state="normal")
        self._tick(duration)

    def _get_adaptive_font(self, text: str) -> Tuple[str, int, str]:
        length = len(text)
        size = Config.BASE_FONT_SIZE
        if length <= 2: size = Config.BASE_FONT_SIZE + 2
        elif length == 3: size = Config.BASE_FONT_SIZE + 1
        elif length == 4: size = Config.BASE_FONT_SIZE - 1
        elif length >= 5: size = Config.BASE_FONT_SIZE - 3
        return (Config.FONT_FAMILY, size, "bold")

    def _draw_outlined_text(self, text):
        self.delete("timer_text")
        cx, cy = Config.ICON_SIZE // 2, Config.ICON_SIZE // 2
        font_spec = self._get_adaptive_font(text)
        offsets = [(-1, -1), (0, -1), (1, -1), (-1,  0), (1,  0), (-1,  1), (0,  1), (1,  1)]
        for ox, oy in offsets:
            self.create_text(cx + ox, cy + oy, text=text, font=font_spec, fill=Config.COLOR_TEXT_OUTLINE, tags="timer_text", anchor="center")
        self.create_text(cx, cy, text=text, font=font_spec, fill=Config.COLOR_TEXT_ACTIVE, tags="timer_text", anchor="center")

    def _tick(self, remaining):
        if remaining <= 0:
            self._reset()
            return
        m, s = divmod(remaining, 60)
        text = f"{m}:{s:02}" if remaining >= 60 else str(remaining)
        self._draw_outlined_text(text)
        self.timer_job = self.after(1000, lambda: self._tick(remaining - 1))

    def _reset(self):
        self.is_active = False
        if self.timer_job: self.after_cancel(self.timer_job)
        self.delete("timer_text")
        self.itemconfig(self.dim_id, state="hidden")

# --- APP ---
class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        # TITLE UPDATED
        self.root.title("Spell Timer") 
        self.root.configure(bg=Config.COLOR_BG)
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", Config.GLOBAL_OPACITY)

        self.game_active = False
        self._img_refs = []
        
        self.saved_x = 0
        self.saved_y = 0
        self.is_pinned = False
        self._load_config()

        self._drag_data = {"x": 0, "y": 0}

        # UI Setup
        self.container = tk.Frame(self.root, bg=Config.COLOR_BORDER, padx=1, pady=1)
        self.container.pack()
        self.inner = tk.Frame(self.container, bg=Config.COLOR_BG, padx=4, pady=4)
        self.inner.pack()

        self.handle = tk.Label(self.inner, text="::::", bg=Config.COLOR_BG, fg=Config.COLOR_HANDLE, font=("Arial", 7, "bold"), cursor="fleur")
        self.handle.pack(fill="x", pady=(0, 2))
        
        self.handle.bind("<ButtonPress-1>", self._start_drag)
        self.handle.bind("<B1-Motion>", self._do_drag)
        self.handle.bind("<Button-3>", self._toggle_pin)
        
        self._update_pin_visual()

        self.enemies_frame = tk.Frame(self.inner, bg=Config.COLOR_BG)
        self.enemies_frame.pack()

        self.root.withdraw()
        
        # Start Tray
        self._setup_tray()
        
        # Handle CTRL+C
        signal.signal(signal.SIGINT, self._graceful_exit)
        
        self._monitor_game_loop()

    def _setup_tray(self):
        """Starts the tray icon in a separate thread."""
        def quit_app(icon, item):
            print("[Tray] Quitting...")
            self._save_config()
            icon.stop()
            self.root.quit()
            sys.exit(0)

        # 1. Try to load custom icon.ico
        custom_icon = resource_path("ico/icon.ico")
        # 2. Fallback to Flash icon
        flash_icon = resource_path("assets/spells/SummonerFlash.png")
        
        image = None
        if os.path.exists(custom_icon):
            try:
                image = Image.open(custom_icon)
            except: pass
            
        if image is None and os.path.exists(flash_icon):
            image = Image.open(flash_icon)
            
        if image is None:
            image = Image.new('RGB', (64, 64), color=(255, 255, 0))

        menu = pystray.Menu(pystray.MenuItem("Quit", quit_app))
        # NAME UPDATED
        self.tray_icon = pystray.Icon("SpellTimer", image, "Spell Timer", menu)
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _load_config(self):
        if os.path.exists(Config.CONFIG_FILE):
            try:
                with open(Config.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.saved_x = data.get('x', 0)
                    self.saved_y = data.get('y', 0)
                    self.is_pinned = data.get('pinned', False)
                    print(f"[Config] Loaded: Pos({self.saved_x},{self.saved_y}), Pinned({self.is_pinned})")
            except Exception as e:
                print(f"[Config] Load error: {e}")
        else:
            sw = self.root.winfo_screenwidth()
            self.saved_x = sw - 250
            self.saved_y = 100

    def _save_config(self):
        data = {
            'x': self.saved_x,
            'y': self.saved_y,
            'pinned': self.is_pinned
        }
        try:
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            print("[Config] Saved settings.")
        except Exception as e:
            print(f"[Config] Save error: {e}")

    def _graceful_exit(self, signum, frame):
        print("\n[Spell Timer] Stopping...")
        self._save_config()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.destroy()
        sys.exit(0)

    def _toggle_pin(self, event):
        self.is_pinned = not self.is_pinned
        self._update_pin_visual()
        self._save_config()

    def _update_pin_visual(self):
        if self.is_pinned:
            self.handle.config(text="🔒 PINNED", fg=Config.COLOR_PINNED, cursor="arrow")
        else:
            self.handle.config(text="::::", fg=Config.COLOR_HANDLE, cursor="fleur")

    def _monitor_game_loop(self):
        data = GameDataManager.fetch_data()
        if data:
            if not self.game_active:
                print("[Spell Timer] Match found!")
                self._build_enemy_rows(data)
                self.root.deiconify()
                
                self.root.geometry(f"+{self.saved_x}+{self.saved_y}")
                
                self.root.after(100, self._apply_native_styles)
                self.game_active = True
        else:
            if self.game_active:
                print("[Spell Timer] Match ended.")
                self.root.withdraw()
                self._save_config()
                self.game_active = False
        self.root.after(Config.CHECK_INTERVAL, self._monitor_game_loop)

    def _build_enemy_rows(self, data):
        for widget in self.enemies_frame.winfo_children(): widget.destroy()
        self._img_refs.clear()

        enemies = GameDataManager.parse_enemies(data)
        if not enemies: return

        for i, enemy in enumerate(enemies):
            if i > 0 and Config.SHOW_SEPARATOR:
                sep = tk.Frame(self.enemies_frame, bg=Config.COLOR_SEPARATOR, height=1)
                sep.pack(fill="x", padx=10, pady=2)

            row = tk.Frame(self.enemies_frame, bg=Config.COLOR_BG)
            row.pack(fill="x", pady=Config.ROW_PADDING_Y)

            champ_icon = AssetManager.load_icon("champions", enemy['champ'], (Config.ICON_SIZE, Config.ICON_SIZE), is_round=True)
            self._img_refs.append(champ_icon)
            lbl = tk.Label(row, image=champ_icon, bg=Config.COLOR_BG, bd=0)
            lbl.pack(side="left", padx=(0, 8))

            for s_name in [enemy['spell1'], enemy['spell2']]:
                sw = SpellTimerWidget(row, s_name)
                sw.pack(side="left", padx=3)
                self._img_refs.append(sw.icon_img)
                self._img_refs.append(sw.dim_img)

    def _apply_native_styles(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if hwnd == 0: hwnd = self.root.winfo_id()
        Win32Utils.set_no_focus(hwnd)

    def _start_drag(self, event):
        if self.is_pinned: return 
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _do_drag(self, event):
        if self.is_pinned: return
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        
        self.root.geometry(f"+{x}+{y}")
        self.saved_x = x
        self.saved_y = y

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    DDragonManager.update_timers()
    app = OverlayApp()
    app.run()