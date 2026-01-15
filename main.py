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

# --- SINGLE INSTANCE CHECKER (MUTEX) ---
class SingleInstanceChecker:
    """Prevents multiple instances of the application."""
    def __init__(self, app_name="Global\\LoLSpellTimer_v9_5"):
        self.mutex_name = app_name
        self.mutex = None

    def is_already_running(self):
        kernel32 = ctypes.windll.kernel32
        self.mutex = kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return True
        return False

# --- RESOURCE HELPER ---
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- CONFIGURATION ---
class Config:
    if getattr(sys, 'frozen', False):
        APP_DIR = os.path.dirname(sys.executable)
    else:
        APP_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_FILE = os.path.join(APP_DIR, "config.json")

    # === ITEM DATABASE (SUMMONER SPELL HASTE) ===
    # Item ID -> Haste Value
    ITEM_HASTE_MAP = {
        3158: 10,    # Ionian Boots of Lucidity (SR/ARAM) -> 10 Haste
        3171: 20,    # Crimson Lucidity (Ornn Upgrade) -> 20 Haste
        223158: 10,  # Ionian Boots (Arena) -> 10 Haste
    }

    # === BASE SPELL TIMERS (Seconds) ===
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
    
    COLOR_PINNED = "#8B0000"    # Dark Red
    COLOR_HANDLE = "#666666"    # Grey
    
    FONT_FAMILY = "Arial"     
    BASE_FONT_SIZE = 12         
    
    # API URLs
    LCL_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
    DDRAGON_VER_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
    DDRAGON_DATA_URL = "https://ddragon.leagueoflegends.com/cdn/{}/data/en_US/summoner.json"
    
    CHECK_INTERVAL = 2000 # Check every 2 seconds

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
            
            # --- CALCULATE HASTE (ITEMS ONLY) ---
            items = p.get("items", [])
            current_haste = 0
            
            for item in items:
                i_id = item.get("itemID", 0)
                # Add haste if item is in our database
                val = Config.ITEM_HASTE_MAP.get(i_id, 0)
                current_haste += val
            
            enemies.append({
                "champ": champ_name,
                "spell1": GameDataManager._clean_spell_name(spells.get("summonerSpellOne", {}).get("rawDisplayName")),
                "spell2": GameDataManager._clean_spell_name(spells.get("summonerSpellTwo", {}).get("rawDisplayName")),
                "haste": current_haste 
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
            {"champ": "Darius", "spell1": "SummonerFlash", "spell2": "SummonerTeleport", "haste": 0},
            {"champ": "Ornn", "spell1": "SummonerFlash", "spell2": "SummonerTeleport", "haste": 20},
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

# --- SPELL TIMER WIDGET ---
class SpellTimerWidget(tk.Canvas):
    def __init__(self, parent, champ_name: str, spell_name: str, app_ref):
        super().__init__(parent, width=Config.ICON_SIZE, height=Config.ICON_SIZE, 
                         bg=Config.COLOR_BG, highlightthickness=0)
        self.champ_name = champ_name
        self.spell_name = spell_name
        self.app_ref = app_ref # Reference to main app to access cache
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
        base_cd = Config.SPELL_TIMERS.get(key, 300)
        
        # --- CALCULATE COOLDOWN WITH HASTE ---
        # Get current haste from app cache (updated in background)
        current_haste = self.app_ref.get_haste(self.champ_name)
        
        # Formula: ReducedCooldown = Base * (100 / (100 + Haste))
        if current_haste > 0:
            final_cd = base_cd * (100 / (100 + current_haste))
            final_cd = int(final_cd)
            print(f"[Timer] {self.champ_name} ({self.spell_name}): Base {base_cd}s -> Haste {current_haste} -> {final_cd}s")
        else:
            final_cd = base_cd

        self._start_timer(final_cd)

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

# --- MAIN APP ---
class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Spell Timer") 
        self.root.configure(bg=Config.COLOR_BG)
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", Config.GLOBAL_OPACITY)

        self.game_active = False
        self.enemy_data_cache = {} # Cache to store fresh enemy data
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
        
        self._setup_tray()
        
        signal.signal(signal.SIGINT, self._graceful_exit)
        
        self._monitor_game_loop()

    def get_haste(self, champ_name: str) -> int:
        """Returns the current haste for a specific champion from cache."""
        data = self.enemy_data_cache.get(champ_name, {})
        return data.get('haste', 0)

    def _setup_tray(self):
        def quit_app(icon, item):
            print("[Tray] Quitting...")
            self._save_config()
            icon.stop()
            self.root.quit()
            sys.exit(0)

        custom_icon = resource_path("ico/icon.ico")
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
            print("[Config] Settings saved.")
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
            # 1. Parse enemies and update cache with fresh data (items/haste)
            enemies = GameDataManager.parse_enemies(data)
            for enemy in enemies:
                self.enemy_data_cache[enemy['champ']] = enemy
            
            # 2. Build UI only if game just started
            if not self.game_active:
                print("[Spell Timer] Match found!")
                self._build_enemy_rows(enemies)
                self.root.deiconify()
                self.root.geometry(f"+{self.saved_x}+{self.saved_y}")
                self.root.after(100, self._apply_native_styles)
                self.game_active = True
            
            # NOTE: We do NOT rebuild UI in loop to preserve running timers.
            # Haste data is fetched from cache dynamically on click.
            
        else:
            if self.game_active:
                print("[Spell Timer] Match ended.")
                self.root.withdraw()
                self._save_config()
                self.game_active = False
                self.enemy_data_cache.clear()
                
        self.root.after(Config.CHECK_INTERVAL, self._monitor_game_loop)

    def _build_enemy_rows(self, enemies: List[Dict]):
        # Full rebuild (only on game start)
        for widget in self.enemies_frame.winfo_children(): widget.destroy()
        self._img_refs.clear()

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
                # Pass 'self' (app) reference so the button can query cache
                sw = SpellTimerWidget(row, enemy['champ'], s_name, self)
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
    checker = SingleInstanceChecker()
    if checker.is_already_running():
        sys.exit(0)

    DDragonManager.update_timers()
    app = OverlayApp()
    app.run()