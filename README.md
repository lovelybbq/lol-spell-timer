# Spell Timer

Small Windows overlay that displays enemy summoner spell cooldowns for League of Legends.

![Screenshot](screenshot/screenshot.png)



## Quick start

1. Run setup (creates a virtual environment and installs dependencies):

```cmd
setup.bat
```

2. Download assets (icons):

```bash
python download_assets.py
```

3. Run the app:

```bash
python main.py
```


## Build (Windows)

To build a single-file executable via PyInstaller:

```cmd
build_exe.bat
```

Ensure `ico\\icon.ico` exists before building.

---

## Behavior & notes

- The app runs in the system tray after launch (use the tray menu to quit).
- It auto-detects when a game starts and shows enemy summoner spells; it hides the overlay when the game ends.
- The overlay remembers and restores its last position (saved in `config.json`).
- Right-click the drag handle to pin/unpin the overlay.
- Right-click an active spell icon to immediately reset its cooldown.
- Cooldown calculations include enemy item "haste" (see `Config.ITEM_HASTE_MAP` in `main.py`).
- All behaviors above apply both to the built EXE and when running `main.py` directly.

