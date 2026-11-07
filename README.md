# ✧ Smug Guild Board ✧
### `LinuxMint_Python3_RpgInspired_Dynamic_ToDoList`

An interactive, Conky-style RPG guild quest board to-do widget for **Linux Mint (Xfce / X11)** built with **Python 3** and **PyQt6**.

![Platform](https://img.shields.io/badge/Platform-Linux%20Mint%20%2F%20X11-FF85A2?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-D8B4F8?style=flat-square)
![GUI](https://img.shields.io/badge/PyQt6-Desktop%20Widget-FFB7C5?style=flat-square)

---

## ✿ Overview & Features

**Smug Guild Board** sits directly on your X11 desktop wallpaper layer like Conky — ignoring `Alt+Tab` and staying out of your panel taskbar — while giving you a fully interactive, kawaii JRPG-inspired quest tracker:

- **Pinned X11 Desktop Layer:** Frameless, translucent glass HUD using `WindowStaysOnBottomHint` + `wmctrl` (`sticky`, `skip_taskbar`, `skip_pager`, `below`).
- **Editable Board Display Name:** Click the **`✧ Smug Guild Board ✧`** header title directly (or right-click → **`✦ Rename board…`**) to set your own custom board name, with one-click reset to default.
- **JRPG Priority Ranks & Live Countdown Timers:**
  - `✦ S-Rank`, `✿ A-Rank`, `❀ B-Rank`, and `⋆ C-Rank` pastel pill badges.
  - Live `1s` countdown timers that shift color as deadlines approach and pulse **`♥ OVERDUE !`** under 1 hour.
- **Proportional Scaling (`55%` – `115%`):** Scale the entire board cleanly from **`55% · Tiny`** up to **`115% · Large`** so it fits everything from `1366x768` laptop screens to ultrawide monitors.
- **Dual Glass Themes & Colored ASCII Mascots:**
  - Switch between **Berry Glass** (dark frosted rose) and **Sakura Cream** (soft light pastel).
  - Click the top-left `bunnyfetch`-style ASCII mascot to cycle between **Pastel Bunny**, **Cozy Neko**, and **Pink Mint / Arch Crest**.
- **Pin Position Memory & Autorun at Boot:**
  - Drag the header anywhere, click **`( Pin: Off ✧ )` → `( Pin: On ♡ )`** to lock and persist exact `(x, y)` coordinates across restarts.
  - Toggle **`♡ Autorun at boot`** right from the right-click sidemenu (`~/.config/autostart/smug-guild-board.desktop`).
- **Sparkle Quest Clear Animation:** Click `( ♡ )` → `( ♥ )` to trigger a **`✧ ˖ ° ♡ Q U E S T C L E A R ! ♡ ° ˖ ✧`** fade-out and archive into a collapsible **Completed Quests** log.

---

## ✧ 1. How to Install & Run

### Prerequisites (Linux Mint / Ubuntu / Debian)
Install Python 3, PyQt6, and standard X11 helper utilities:

```bash
sudo apt update && sudo apt install -y python3 python3-pyqt6 wmctrl x11-utils
```
*(Alternatively, inside a virtual environment: `pip install PyQt6`)*

### Clone & Launch
```bash
git clone https://github.com/Renz-Amorganda/LinuxMint_Python3_RpgInspired_Dynamic_ToDoList.git
cd LinuxMint_Python3_RpgInspired_Dynamic_ToDoList
python3 smug_guild_board.py
```

### Run Detached in the Background
If you want to launch the widget and close your terminal afterward:
```bash
nohup python3 smug_guild_board.py >/dev/null 2>&1 &
```

### Enable Autorun on Login
1. Launch the widget once (`python3 smug_guild_board.py`).
2. **Right-click** anywhere on the board → click **`♡ Autorun at boot`**.
3. This creates `~/.config/autostart/smug-guild-board.desktop` with an automatic login settle delay so Xfce panels and wallpaper load cleanly before the board pins itself.

> **Tip — Frosted Glass Transparency on Xfce:**
> For translucent glass backgrounds on Linux Mint Xfce, enable **Menu → Settings → Window Manager Tweaks → Compositor → Enable display compositing**. If compositing is disabled, the board automatically falls back to crisp rounded XShape corners.

---

## ♡ 2. How to Use the Widget

### Posting, Clearing & Managing Quests
- **Add a New Quest:** Click **`[ + New Quest ♡ ]`** (or right-click → **`♡ New quest`**):
  1. Type your quest title (press `Enter` anytime to submit, or `Esc` to cancel).
  2. Pick a priority badge: **`✦ S`**, **`✿ A`**, **`❀ B`**, or **`⋆ C`**.
  3. Pick a quick deadline preset (**`+2h`**, **`+6h`**, **`+1d`**, **`+3d`**, **`+7d`**) **or** type an exact timestamp (`YYYY-MM-DD HH:MM`, e.g. `2026-11-15 18:30`).
  4. Click **`[ Accept Quest ♡ ]`**.
- **Complete a Quest:** Click the **`( ♡ )`** heart checkbox on the left of any quest to play the **`QUEST CLEAR!`** animation and move it to **`✿ Completed Quests (X)`** at the bottom.
- **Clear Completed History:** Click **`✿ Completed Quests (X) ▸`** to expand your archive, then click **`[ Clear History ✧ ]`**.
- **Abandon / Delete a Quest:** Click the small **`×`** on the right of a quest row once (`× sure?`), then click a second time within `2.5s` to permanently remove it.

### Customizing Appearance & Layout
| Action | How to Trigger |
| :--- | :--- |
| **Rename Board Title** | Click **`✧ Smug Guild Board ✧`** in the header **or** Right-click → **`✦ Rename board…`** (`[ Default ✿ ]` resets it) |
| **Move & Lock Position** | Make sure pin is **`( Pin: Off ✧ )`**, drag the top header bar, then click **`( Pin: On ♡ )`** to lock & save `(x, y)` |
| **Scale Board Size** | Click **`( 100% ⋆ )`**, Right-click → **`⋆ Board Size`** (`55%`–`115%`), or press `Ctrl+-` / `Ctrl+=` / `Ctrl+0` |
| **Switch Glass Theme** | Click **`( Berry ✦ )`** / **`( Cream ✿ )`** in the header **or** Right-click → **`✿ Switch theme`** |
| **Change ASCII Mascot** | Left-click the colored ASCII art mascot in the top-left corner |
| **Sort Quests** | Click **`( ▾ Rank ♡ )`**, **`( Time ✧ )`**, or **`( Name ✿ )`** (click the active pill again to flip `▾` / `▴`) |
| **Reload from Disk** | Click **`[ ↻ Resync ✿ ]`** **or** Right-click → **`↻ Resync quests`** |
| **Close the Widget** | Right-click anywhere on the board → **`× Close board`** |

---

## ⋆ 3. How to Edit Quests, Settings & Code

### A. Editing Quests Directly (`quests.json`)
On first run, `quests.json` is created in the project folder. You can edit it with any text editor or external script while the board is running, then click **`[ ↻ Resync ✿ ]`** on the widget to reload instantly:

```json
[
  {
    "id": "8512eb145d9f",
    "title": "Finish Linux Mint rice & dotfiles",
    "rank": "S",
    "deadline": "2026-11-12T19:30:00",
    "completed": false
  }
]
```
- **`rank`**: `"S"`, `"A"`, `"B"`, or `"C"`
- **`deadline`**: ISO 8601 local timestamp (`YYYY-MM-DDTHH:MM:SS`)
- **`completed`**: `true` or `false`

*(If `quests.json` ever gets corrupted by a manual edit, the widget automatically backs it up as `quests.broken-YYYYMMDD-HHMMSS.json` so you never lose your text.)*

### B. Editing Saved Preferences (`smug_settings.json`)
Your UI state is stored locally in `smug_settings.json` (git-ignored so personal screen coordinates stay local):

```json
{
  "board_name": "Smug Guild Board",
  "theme": "berry",
  "pinned": true,
  "scale": 0.85,
  "sort_key": "rank",
  "sort_asc": true,
  "mascot": 0,
  "completed_open": false,
  "x": 964,
  "y": 278
}
```

### C. Customizing Colors, Mascots & Presets in `smug_guild_board.py`
Everything lives cleanly in a single self-contained script (`smug_guild_board.py`) so hacking on it is straightforward:
- **Board Dimensions & Scale Presets:** Edit `BASE_BOARD_WIDTH` and `SCALE_PRESETS` near the top of `smug_guild_board.py`.
- **Deadline Presets:** Edit `DEADLINE_PRESETS` (`+2h`, `+6h`, `+1d`, `+3d`, `+7d`) to add your own quick time buttons.
- **Themes & Rank Badge Colors:** Edit the `PALETTES` dictionary (`"berry"` and `"cream"`) to tweak background RGBA alpha, border hex codes, or `S`/`A`/`B`/`C` badge colors.
- **Custom ASCII Art Mascots:** Edit the `MASCOTS` list — each mascot has a `"normal"` and `"cheer"` multi-line array of `(text, palette_color_key)` tuples. After editing `smug_guild_board.py`, simply close and re-run `python3 smug_guild_board.py` to see your changes.

---

*© programmed by smugdealer ♡*
