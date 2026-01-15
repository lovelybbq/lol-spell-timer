"""
Smart Asset Downloader for LoL Tracker.
Checks for LoL updates via DDragon.
- If version changed: Redownloads ALL assets to ensure latest art.
- If version same: Downloads only MISSING assets.
"""

import os
import requests
import shutil

# --- CONFIGURATION ---
ASSETS_DIR = "assets"
CHAMP_DIR = os.path.join(ASSETS_DIR, "champions")
SPELL_DIR = os.path.join(ASSETS_DIR, "spells")
VERSION_FILE = os.path.join(ASSETS_DIR, "version.txt")

# Spells list
SPELL_IDS = [
    "SummonerFlash", "SummonerDot", "SummonerHeal", "SummonerBarrier", "SummonerExhaust",
    "SummonerTeleport", "SummonerSmite", "SummonerBoost", "SummonerMana", "SummonerHaste", "SummonerSnowball"
]

def get_latest_version():
    """Fetches the latest DDragon version (e.g., '14.2.1')."""
    try:
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()[0]
    except Exception as e:
        print(f"[Error] Could not fetch DDragon version: {e}")
        return None

def get_local_version():
    """Reads the locally stored version from version.txt."""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return None

def save_local_version(version):
    """Saves the current version to version.txt."""
    with open(VERSION_FILE, "w") as f:
        f.write(version)

def get_champion_list(version):
    """Fetches the list of all champion names for the specific version."""
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return list(data['data'].keys())
    except Exception as e:
        print(f"[Error] Could not fetch champion list: {e}")
        return []

def download_file(url, path, force=False):
    """
    Downloads a file.
    :param force: If True, overwrites existing file.
    """
    if os.path.exists(path) and not force:
        # File exists and we don't want to force update
        return False
    
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            print(f" [+] Downloaded: {os.path.basename(path)}")
            return True
        else:
            print(f" [!] Failed (Status {resp.status_code}): {url}")
            return False
    except Exception as e:
        print(f" [!] Error downloading {url}: {e}")
        return False

def create_placeholder():
    """Creates a placeholder image if Pillow is available."""
    placeholder_path = os.path.join(ASSETS_DIR, "placeholder.png")
    if os.path.exists(placeholder_path):
        return

    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (40, 40), (40, 40, 40, 255))
        draw = ImageDraw.Draw(img)
        # Draw a simple '?' or border
        draw.rectangle([0, 0, 39, 39], outline=(100, 100, 100))
        draw.text((15, 10), "?", fill=(200, 200, 200))
        img.save(placeholder_path)
        print(" [i] Created placeholder.png")
    except ImportError:
        print(" [!] Pillow not installed. Skipping placeholder generation.")
    except Exception:
        pass # Font issues usually

def main():
    # 1. Setup Directories
    os.makedirs(CHAMP_DIR, exist_ok=True)
    os.makedirs(SPELL_DIR, exist_ok=True)

    # 2. Check Version
    print("--- LoL Asset Manager ---")
    latest_ver = get_latest_version()
    if not latest_ver:
        print("Could not connect to Riot API. Exiting.")
        return

    local_ver = get_local_version()
    
    force_update = False
    
    if local_ver != latest_ver:
        print(f" [!] Update detected! Local: {local_ver} -> Latest: {latest_ver}")
        print(" [i] Doing a full sync...")
        force_update = True
    else:
        print(f" [OK] Version {latest_ver} is up to date.")
        print(" [i] Checking for missing files only...")

    # 3. Download Champions
    print("\n--- Syncing Champions ---")
    champs = get_champion_list(latest_ver)
    if not champs:
        print("Failed to get champion list.")
        return

    for champ in champs:
        url = f"https://ddragon.leagueoflegends.com/cdn/{latest_ver}/img/champion/{champ}.png"
        path = os.path.join(CHAMP_DIR, f"{champ}.png")
        # Special case: Fiddlesticks in DDragon is just "Fiddlesticks", but sometimes API refers differently. 
        # Usually DDragon names match the key.
        download_file(url, path, force=force_update)

    # 4. Download Spells
    print("\n--- Syncing Spells ---")
    for spell in SPELL_IDS:
        url = f"https://ddragon.leagueoflegends.com/cdn/{latest_ver}/img/spell/{spell}.png"
        path = os.path.join(SPELL_DIR, f"{spell}.png")
        download_file(url, path, force=force_update)

    # 5. Finalize
    save_local_version(latest_ver)
    create_placeholder()
    print(f"\n[Success] All assets synced for version {latest_ver}!")

if __name__ == "__main__":
    main()