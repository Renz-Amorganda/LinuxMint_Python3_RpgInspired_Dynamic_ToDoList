#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
✧ Smug Guild Board ✧
A kawaii pastel-pink RPG-inspired "guild quest board" to-do widget pinned to
the X11 desktop (Linux Mint Xfce / xfwm4) — like Conky, but interactive.

Programmed by smugdealer.

Run:    python3 smug_guild_board.py
Data:   quests.json         (your quests, created on first launch)
        smug_settings.json  (board name, position, scale, theme, sort, mascot, pin state)

Tips:
  • Click the board title (or right-click → Rename board…) to customize your board's display name.
  • Drag the header to move the board, then click ( Pin: Off ✧ ) to lock & save its spot.
  • Click ( 100% ⋆ ) or right-click → Board Size to scale the board down or up.
  • Click the ASCII mascot to switch between bunny / neko / crest.
  • Right-click anywhere on the board for the sidemenu (Rename, Board Size, Autorun at boot, Pin, Close).
  • Translucency needs a compositor: in Xfce, enable
        Window Manager Tweaks → Compositor → "Enable display compositing"
"""

from __future__ import annotations

import html
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QActionGroup,
    QBitmap,
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

APP_NAME = "Smug Guild Board"
DEFAULT_BOARD_NAME = APP_NAME
MAX_BOARD_NAME_LEN = 36
APP_CREDIT = "© programmed by smugdealer ♡"

APP_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = Path(__file__).resolve()
QUESTS_FILE = APP_DIR / "quests.json"
SETTINGS_FILE = APP_DIR / "smug_settings.json"
LEGACY_SETTINGS_FILE = APP_DIR / "sakura_settings.json"

AUTOSTART_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "smug-guild-board.desktop"
LEGACY_AUTOSTART_FILE = AUTOSTART_DIR / "smug-quest-board.desktop"

BASE_BOARD_WIDTH = 468
BASE_CORNER_RADIUS = 18
BASE_MARGIN_L, BASE_MARGIN_T, BASE_MARGIN_R, BASE_MARGIN_B = 20, 18, 20, 14
BASE_LIST_MAX_HEIGHT = 390
BASE_COMPLETED_MAX_HEIGHT = 130

SCALE_PRESETS: tuple[tuple[float, str], ...] = (
    (0.55, "55% · Tiny"),
    (0.65, "65% · Mini"),
    (0.75, "75% · Compact"),
    (0.85, "85% · Cozy"),
    (1.00, "100% · Normal"),
    (1.15, "115% · Large"),
)
SCALE_VALUES = tuple(val for val, _ in SCALE_PRESETS)

CLEAR_FADE_MS = 550
RESYNC_MS = 600
CHEER_HOLD_MS = 1400
ABANDON_CONFIRM_MS = 2500

RANKS = ("S", "A", "B", "C")
RANK_ORDER = {rank: index for index, rank in enumerate(RANKS)}
RANK_GLYPH = {"S": "✦", "A": "✿", "B": "❀", "C": "⋆"}

SORT_OPTIONS = (("rank", "Rank", "♡"), ("time", "Time", "✧"), ("name", "Name", "✿"))
SPIN_FRAMES = ("✿", "❀", "✧", "✦", "⋆", "✦", "✧", "❀")
DEADLINE_PRESETS = (
    ("+2h", timedelta(hours=2)),
    ("+6h", timedelta(hours=6)),
    ("+1d", timedelta(days=1)),
    ("+3d", timedelta(days=3)),
    ("+7d", timedelta(days=7)),
)
DEFAULT_PRESET = "+1d"
DEFAULT_RANK = "B"
CUSTOM_DEADLINE_FORMAT = "%Y-%m-%d %H:%M"

CLEAR_BANNER = "✧ ˖ ° ♡  Q U E S T   C L E A R !  ♡ ° ˖ ✧"
RESYNC_IDLE_TEXT = "[ ↻ Resync ✿ ]"
NEW_QUEST_TEXT = "[ + New Quest ♡ ]"
NEW_QUEST_OPEN_TEXT = "[ − Close ✧ ]"

DEFAULT_SETTINGS = {
    "board_name": DEFAULT_BOARD_NAME,
    "theme": "berry",
    "pinned": False,
    "scale": 1.0,
    "sort_key": "rank",
    "sort_asc": True,
    "mascot": 0,
    "completed_open": False,
    "x": None,
    "y": None,
}


def px(base: float, scale: float, minimum: int = 1) -> int:
    """Scale a pixel metric cleanly with a safe lower bound."""
    return max(minimum, int(round(base * scale)))


def clean_board_name(raw) -> str:
    """Normalize a user-provided board display name, falling back to DEFAULT_BOARD_NAME."""
    if not isinstance(raw, str):
        return DEFAULT_BOARD_NAME
    cleaned = " ".join(raw.split())[:MAX_BOARD_NAME_LEN]
    return cleaned if cleaned else DEFAULT_BOARD_NAME


# ─────────────────────────────────────────────────────────────────────────────
#  Palettes  (berry = dark rose glass, cream = soft sakura cream)
# ─────────────────────────────────────────────────────────────────────────────

PALETTES = {
    "berry": {
        "bg": (42, 24, 36, 210),
        "border": "#FFB7C5",
        "inner": "#FFE4E1",
        "inner_alpha": 120,
        "sparkle": "#FFE4E1",
        "title": "#FFF5F8",
        "text": "#FFF5F8",
        "sub": "#FFC1D6",
        "muted": "rgba(255, 193, 214, 150)",
        "credit": "rgba(255, 193, 214, 130)",
        "divider": "rgba(255, 228, 225, 90)",
        "row_bg": "rgba(255, 183, 197, 16)",
        "row_hover": "rgba(255, 183, 197, 34)",
        "row_border": "rgba(255, 183, 197, 55)",
        "panel_bg": "rgba(255, 183, 197, 14)",
        "pill_bg": "rgba(255, 183, 197, 22)",
        "pill_hover": "rgba(255, 183, 197, 48)",
        "pill_border": "rgba(255, 183, 197, 120)",
        "pill_text": "#FFC1D6",
        "pill_active_bg": "rgba(255, 133, 162, 80)",
        "pill_active_border": "#FF85A2",
        "pill_active_text": "#FFF5F8",
        "btn_bg": "rgba(255, 133, 162, 38)",
        "btn_hover": "rgba(255, 133, 162, 75)",
        "input_bg": "rgba(255, 245, 248, 18)",
        "heart": "#FFC1D6",
        "heart_on": "#FF69B4",
        "time_far": "#E2C6FF",
        "time_mid": "#FFD1B3",
        "time_soon": "#FFE082",
        "time_over": "#FF4D79",
        "time_over_pulse": "#FF9DB8",
        "banner_c1": "#FF85A2",
        "banner_c2": "#FFE082",
        "banner_bg1": "rgba(255, 105, 180, 40)",
        "banner_bg2": "rgba(255, 224, 130, 55)",
        "banner_border": "#FF85A2",
        "menu_bg": "#2A1824",
        "tooltip_bg": "#2A1824",
        "tooltip_text": "#FFF5F8",
        "m_body": "#FFF5F8",
        "m_cheek": "#FF69B4",
        "m_star": "#FFE082",
        "m_ears": "#FFB7C5",
        "m_crest": "#FF85A2",
        "m_crest2": "#E0B0FF",
        "badges": {
            "S": {"border": "#FF69B4", "text": "#FFE082", "bg": "rgba(255, 105, 180, 45)", "glow": "#FF69B4"},
            "A": {"border": "#FF85A2", "text": "#FFD1DC", "bg": "rgba(255, 133, 162, 30)", "glow": None},
            "B": {"border": "#D8B4F8", "text": "#F3E8FF", "bg": "rgba(216, 180, 248, 28)", "glow": None},
            "C": {"border": "#FFC8A2", "text": "#FFF0E6", "bg": "rgba(255, 200, 162, 26)", "glow": None},
        },
    },
    "cream": {
        "bg": (255, 240, 246, 225),
        "border": "#FFB7C5",
        "inner": "#FFE4E1",
        "inner_alpha": 220,
        "sparkle": "#FF85A2",
        "title": "#8E3B5E",
        "text": "#5C2D45",
        "sub": "#C2577F",
        "muted": "rgba(140, 70, 100, 150)",
        "credit": "rgba(140, 70, 100, 135)",
        "divider": "rgba(255, 133, 162, 110)",
        "row_bg": "rgba(255, 255, 255, 120)",
        "row_hover": "rgba(255, 255, 255, 190)",
        "row_border": "rgba(255, 183, 197, 150)",
        "panel_bg": "rgba(255, 255, 255, 100)",
        "pill_bg": "rgba(255, 183, 197, 50)",
        "pill_hover": "rgba(255, 183, 197, 100)",
        "pill_border": "rgba(255, 133, 162, 150)",
        "pill_text": "#B04A72",
        "pill_active_bg": "rgba(255, 133, 162, 150)",
        "pill_active_border": "#FF6F96",
        "pill_active_text": "#FFFFFF",
        "btn_bg": "rgba(255, 183, 197, 80)",
        "btn_hover": "rgba(255, 133, 162, 130)",
        "input_bg": "rgba(255, 255, 255, 170)",
        "heart": "#E68AA8",
        "heart_on": "#FF3D8B",
        "time_far": "#8A5CC2",
        "time_mid": "#C8682E",
        "time_soon": "#B07D00",
        "time_over": "#E0245E",
        "time_over_pulse": "#FF7AA2",
        "banner_c1": "#FF4F86",
        "banner_c2": "#C99400",
        "banner_bg1": "rgba(255, 183, 197, 120)",
        "banner_bg2": "rgba(255, 224, 130, 140)",
        "banner_border": "#FF85A2",
        "menu_bg": "#FFF0F6",
        "tooltip_bg": "#FFF0F6",
        "tooltip_text": "#5C2D45",
        "m_body": "#9A4D6E",
        "m_cheek": "#FF4F9A",
        "m_star": "#D9A400",
        "m_ears": "#FF85A2",
        "m_crest": "#FF6F96",
        "m_crest2": "#A66BD6",
        "badges": {
            "S": {"border": "#FF69B4", "text": "#B07D00", "bg": "rgba(255, 224, 130, 110)", "glow": "#FF69B4"},
            "A": {"border": "#FF85A2", "text": "#C2185B", "bg": "rgba(255, 209, 220, 160)", "glow": None},
            "B": {"border": "#B98BE6", "text": "#6E3FA3", "bg": "rgba(243, 232, 255, 200)", "glow": None},
            "C": {"border": "#F2A877", "text": "#A3532A", "bg": "rgba(255, 240, 230, 220)", "glow": None},
        },
    },
}

QSS_TEMPLATE = """
QWidget {{
    color: {text};
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
    font-size: {fs_base}px;
}}
QLabel#Mascot {{
    background: transparent;
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: {fs_mascot}px;
}}
QLabel#BoardTitle {{
    color: {title};
    font-size: {fs_title}px;
    font-weight: bold;
    border-radius: 5px;
    padding: 1px 2px;
}}
QLabel#BoardTitle:hover {{
    background: {pill_bg};
    color: {heart_on};
}}
QLabel#BoardSubtitle {{ color: {sub}; font-size: {fs_small}px; }}
QLabel#BoardClock {{ color: {muted}; font-size: {fs_small}px; }}
QLabel#FieldLabel {{ color: {sub}; font-size: {fs_small}px; font-weight: bold; }}
QLabel#StatusLabel {{ color: {muted}; font-size: {fs_tiny}px; }}
QLabel#CreditLabel {{ color: {credit}; font-size: {fs_tiny}px; }}
QLabel#EmptyLabel {{ color: {sub}; font-size: {fs_base}px; padding: {pad_empty}px; }}
QLabel#Hint {{ color: {time_over}; font-size: {fs_small}px; }}
QLabel#DividerGlyph {{ color: {border}; font-size: {fs_small}px; }}
QLabel#CompletedItem {{ color: {muted}; font-size: {fs_small}px; }}
QLabel#QuestTitle {{ color: {text}; font-size: {fs_quest}px; }}
QLabel#QuestTime {{ font-size: {fs_small}px; font-weight: bold; }}
QLabel#ClearBanner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {banner_bg1}, stop:0.5 {banner_bg2}, stop:1 {banner_bg1});
    border: 1px solid {banner_border};
    border-radius: {rad_row}px;
    font-size: {fs_base}px;
    font-weight: bold;
    padding: {pad_banner}px;
}}
QFrame#DividerLine {{ background: {divider}; border: none; }}

QPushButton {{ background: transparent; border: none; color: {sub}; }}
QPushButton#PillButton, QPushButton#SortPill, QPushButton#ChoicePill {{
    background: {pill_bg};
    border: 1px solid {pill_border};
    border-radius: {rad_pill}px;
    padding: {pad_pill_v}px {pad_pill_h}px;
    color: {pill_text};
    font-size: {fs_small}px;
}}
QPushButton#PillButton:hover, QPushButton#SortPill:hover, QPushButton#ChoicePill:hover {{
    background: {pill_hover};
    color: {text};
}}
QPushButton#PillButton[active="true"], QPushButton#SortPill[active="true"], QPushButton#ChoicePill:checked {{
    background: {pill_active_bg};
    border: 1px solid {pill_active_border};
    color: {pill_active_text};
    font-weight: bold;
}}
QPushButton#ResyncButton, QPushButton#NewQuestButton, QPushButton#AcceptButton,
QPushButton#CancelButton, QPushButton#ClearHistoryButton {{
    background: {btn_bg};
    border: 1px solid {border};
    border-radius: {rad_btn}px;
    padding: {pad_btn_v}px {pad_btn_h}px;
    color: {text};
    font-size: {fs_small}px;
    font-weight: bold;
}}
QPushButton#ResyncButton:hover, QPushButton#NewQuestButton:hover, QPushButton#AcceptButton:hover,
QPushButton#CancelButton:hover, QPushButton#ClearHistoryButton:hover {{
    background: {btn_hover};
    border: 1px solid {heart_on};
}}
QPushButton#ResyncButton:pressed, QPushButton#NewQuestButton:pressed, QPushButton#AcceptButton:pressed,
QPushButton#CancelButton:pressed, QPushButton#ClearHistoryButton:pressed {{
    background: {pill_active_bg};
}}
QPushButton#ClearHistoryButton:disabled {{ color: {muted}; border: 1px solid {pill_border}; background: transparent; }}
QPushButton#HeartButton {{ color: {heart}; font-size: {fs_heart}px; font-weight: bold; padding: {pad_heart}px; }}
QPushButton#HeartButton[lit="true"] {{ color: {heart_on}; }}
QPushButton#AbandonButton {{ color: {muted}; font-size: {fs_small}px; padding: 0 2px; }}
QPushButton#AbandonButton:hover, QPushButton#AbandonButton[armed="true"] {{ color: {time_over}; font-weight: bold; }}
QPushButton#CompletedToggle {{ color: {sub}; font-size: {fs_base}px; font-weight: bold; text-align: left; padding: 2px 0; }}
QPushButton#CompletedToggle:hover {{ color: {heart_on}; }}

QFrame#QuestRow {{ background: {row_bg}; border: 1px solid {row_border}; border-radius: {rad_row}px; }}
QFrame#QuestRow:hover {{ background: {row_hover}; border: 1px solid {pill_border}; }}
QWidget#RowContent {{ background: transparent; }}
QFrame#Creator, QFrame#RenameBox, QFrame#CompletedBox {{ background: {panel_bg}; border: 1px solid {row_border}; border-radius: {rad_row}px; }}

QLineEdit {{
    background: {input_bg};
    border: 1px solid {pill_border};
    border-radius: {rad_input}px;
    padding: {pad_input_v}px {pad_input_h}px;
    color: {text};
    selection-background-color: {pill_active_bg};
    font-size: {fs_base}px;
}}
QLineEdit:focus {{ border: 1px solid {heart_on}; }}
QLineEdit[error="true"] {{ border: 1px solid {time_over}; }}

QScrollArea, QWidget#ListContainer, QWidget#CompletedList, QWidget#qt_scrollarea_viewport {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{ background: transparent; width: {sb_width}px; margin: 2px 0; }}
QScrollBar::handle:vertical {{ background: {pill_border}; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {heart_on}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QMenu {{
    background: {menu_bg};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
    color: {text};
    font-size: 11px;
}}
QMenu::item {{ padding: 4px 16px; border-radius: 6px; }}
QMenu::item:selected {{ background: {pill_active_bg}; color: {pill_active_text}; }}
QMenu::separator {{ height: 1px; background: {divider}; margin: 4px 8px; }}
QToolTip {{ background: {tooltip_bg}; color: {tooltip_text}; border: 1px solid {border}; padding: 4px; font-size: 11px; }}
"""


def build_stylesheet(pal: dict, scale: float) -> str:
    flat = {key: value for key, value in pal.items() if isinstance(value, str)}
    metrics = {
        "fs_base": px(11, scale, 7),
        "fs_mascot": px(10, scale, 6),
        "fs_title": px(14, scale, 8),
        "fs_quest": px(12, scale, 8),
        "fs_small": px(10, scale, 6),
        "fs_tiny": px(9, scale, 6),
        "fs_heart": px(13, scale, 8),
        "rad_row": px(12, scale, 7),
        "rad_pill": px(7, scale, 4),
        "rad_btn": px(8, scale, 4),
        "rad_input": px(9, scale, 5),
        "pad_pill_v": px(2, scale, 1),
        "pad_pill_h": px(8, scale, 4),
        "pad_btn_v": px(3, scale, 1),
        "pad_btn_h": px(9, scale, 5),
        "pad_input_v": px(4, scale, 2),
        "pad_input_h": px(8, scale, 4),
        "pad_banner": px(6, scale, 3),
        "pad_empty": px(14, scale, 6),
        "pad_heart": px(2, scale, 1),
        "sb_width": px(6, scale, 4),
    }
    return QSS_TEMPLATE.format(**flat, **metrics)


# ─────────────────────────────────────────────────────────────────────────────
#  ASCII mascots  — each line is a list of (text, palette-colour-key) segments
# ─────────────────────────────────────────────────────────────────────────────

MASCOTS = [
    {
        "name": "Pastel Bunny",
        "normal": [
            [(" (\\    /)", "m_body")],
            [("( ", "m_body"), ("˶", "m_cheek"), ("• ᴗ •", "m_body"), ("˶", "m_cheek"), (" )", "m_body")],
            [(" / >", "m_body"), ("✦", "m_star")],
            [('c(")_(")', "m_body")],
        ],
        "cheer": [
            [(" (\\    /)", "m_body")],
            [("( ", "m_body"), ("˶", "m_cheek"), ("ˆ ᗜ ˆ", "m_body"), ("˶", "m_cheek"), (" )", "m_body")],
            [(" ⋆ ", "m_star"), ("\\ ", "m_body"), ("✦", "m_star"), (" /", "m_body"), (" ⋆", "m_star")],
            [('c(")_(")', "m_body")],
        ],
    },
    {
        "name": "Cozy Neko",
        "normal": [
            [(" /\\", "m_ears"), ("_____", "m_body"), ("/\\", "m_ears")],
            [("( ", "m_body"), ("˶", "m_cheek"), ("• ༝ •", "m_body"), ("˶", "m_cheek"), (" )", "m_body")],
            [(" (  っ", "m_body"), ("♡", "m_cheek"), ("c )", "m_body")],
            [("   ∪   ∪", "m_body")],
        ],
        "cheer": [
            [(" /\\", "m_ears"), ("_____", "m_body"), ("/\\", "m_ears")],
            [("( ", "m_body"), ("˶", "m_cheek"), ("ˆ ᗜ ˆ", "m_body"), ("˶", "m_cheek"), (" )", "m_body")],
            [("✧", "m_star"), ("(  っ", "m_body"), ("♡", "m_cheek"), ("c )", "m_body"), ("✧", "m_star")],
            [("   ∪   ∪", "m_body")],
        ],
    },
    {
        "name": "Pink Mint / Arch Crest",
        "normal": [
            [("    /\\", "m_crest"), ("   ✿", "m_crest2")],
            [("   /  \\", "m_crest"), (" ✧ ⋆", "m_crest2")],
            [("  / /\\ \\", "m_crest"), ("  ♡", "m_cheek")],
            [(" / ____ \\", "m_crest2")],
            [("/_/    \\_\\", "m_crest2"), (" ✧", "m_crest")],
        ],
        "cheer": [
            [("    /\\", "m_crest"), ("   ✦", "m_star")],
            [("( ", "m_body"), ("˶", "m_cheek"), ("ˆ ᗜ ˆ", "m_body"), ("˶", "m_cheek"), (" )", "m_body")],
            [("  / /\\ \\", "m_crest"), ("  ♥", "m_cheek")],
            [(" / ____ \\", "m_crest2")],
            [("/_/    \\_\\", "m_crest2"), (" ✿", "m_crest")],
        ],
    },
]


def render_mascot(lines: list, pal: dict, scale: float) -> str:
    fs = px(10, scale, 6)
    lh = px(13, scale, 8)
    cross_span = f'<span style="font-size:{max(4, fs - 4)}px;">༝</span>'
    rows = []
    for line in lines:
        spans = "".join(
            f'<span style="color:{pal[key]};">'
            f'{html.escape(text, quote=False).replace(" ", "&nbsp;").replace("༝", cross_span)}'
            "</span>"
            for text, key in line
        )
        rows.append(
            f'<p style="margin:0; line-height:{lh}px;'
            f" font-family:'DejaVu Sans Mono', 'Noto Sans Mono', monospace; font-size:{fs}px;\">"
            f"{spans}</p>"
        )
    return "".join(rows)


def render_banner(pal: dict) -> str:
    parts = []
    index = 0
    for char in CLEAR_BANNER:
        if char == " ":
            parts.append("&nbsp;")
            continue
        color = pal["banner_c1"] if index % 2 == 0 else pal["banner_c2"]
        index += 1
        parts.append(f'<span style="color:{color};">{html.escape(char)}</span>')
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Time, X11 & Autostart helpers
# ─────────────────────────────────────────────────────────────────────────────


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def parse_deadline(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def to_iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat(timespec="seconds")


def describe_remaining(deadline: datetime, now: datetime, pal: dict, pulse: bool) -> tuple[str, str]:
    seconds = (deadline - now).total_seconds()
    if seconds < 3600:
        return "♥ OVERDUE !", pal["time_over_pulse"] if pulse else pal["time_over"]
    total_minutes = int(seconds // 60)
    days, remainder = divmod(total_minutes, 1440)
    hours, minutes = divmod(remainder, 60)
    if seconds < 24 * 3600:
        return f"✧ {hours}h {minutes:02d}m !", pal["time_soon"]
    if seconds < 72 * 3600:
        return f"❀ {days}d {hours}h", pal["time_mid"]
    return f"⋆ {days}d left", pal["time_far"]


def is_x11_composited() -> bool:
    """Detect whether an X11 compositor is running so corners stay clean either way."""
    if QGuiApplication.platformName() != "xcb":
        return True
    if shutil.which("xprop") is None:
        return True
    try:
        proc = subprocess.run(
            ["xprop", "-root", "_NET_WM_CM_S0"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        out = proc.stdout.strip()
        return "0x" in out and not out.endswith("0x0")
    except (OSError, subprocess.SubprocessError):
        return True


def _desktop_quote(arg: str) -> str:
    """Quote an Exec argument according to the freedesktop Desktop Entry specification."""
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return f'"{escaped}"'


def _autostart_entry_active(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for raw_line in content.splitlines():
        line = raw_line.strip().lower().replace(" ", "")
        if line in ("hidden=true", "x-gnome-autostart-enabled=false", "x-xfce-autostart-enabled=false"):
            return False
    return True


def is_autorun_enabled() -> bool:
    """Check whether XDG / Xfce autostart at login is currently active."""
    return _autostart_entry_active(AUTOSTART_FILE) or _autostart_entry_active(LEGACY_AUTOSTART_FILE)


def set_autorun_enabled(enable: bool, display_name: str = APP_NAME) -> tuple[bool, str]:
    """Create or remove ~/.config/autostart/smug-guild-board.desktop."""
    if not enable:
        try:
            for path in (AUTOSTART_FILE, LEGACY_AUTOSTART_FILE):
                if path.exists():
                    path.unlink()
            return True, "✧ autorun at boot: OFF"
        except OSError as exc:
            return False, f"✧ couldn't disable autorun ({exc.strerror})"

    safe_name = clean_board_name(display_name).replace("\n", " ").replace("\r", " ")
    python_bin = sys.executable or "/usr/bin/python3"
    exec_line = f"{_desktop_quote(python_bin)} {_desktop_quote(str(SCRIPT_PATH))} --autostart"
    desktop_entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={safe_name}\n"
        "Comment=Interactive kawaii RPG desktop guild board widget by smugdealer\n"
        f"Exec={exec_line}\n"
        f"Path={APP_DIR}\n"
        "Terminal=false\n"
        "StartupNotify=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Hidden=false\n"
        "Categories=Utility;\n"
    )
    try:
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        tmp = AUTOSTART_FILE.with_name(AUTOSTART_FILE.name + ".tmp")
        tmp.write_text(desktop_entry, encoding="utf-8")
        os.replace(tmp, AUTOSTART_FILE)
        if LEGACY_AUTOSTART_FILE.exists() and LEGACY_AUTOSTART_FILE != AUTOSTART_FILE:
            try:
                LEGACY_AUTOSTART_FILE.unlink()
            except OSError:
                pass
        return True, "♥ autorun at boot: ON"
    except OSError as exc:
        return False, f"✧ couldn't enable autorun ({exc.strerror})"


# ─────────────────────────────────────────────────────────────────────────────
#  Persistence
# ─────────────────────────────────────────────────────────────────────────────


def atomic_write_json(path: Path, data) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp_path, path)


def new_quest_id() -> str:
    return uuid.uuid4().hex[:12]


def sample_quests() -> list[dict]:
    now = now_local()
    specs = [
        ("Defeat the Laundry Slime before it evolves", "S", timedelta(minutes=45)),
        ("Brew a matcha potion & study for the guild exam", "A", timedelta(hours=20)),
        ("Customize the Smug Guild Board title & pin spot", "A", timedelta(days=1, hours=6)),
        ("Water the sakura bonsai and whisper encouragement", "B", timedelta(days=2, hours=4)),
        ("Restock the strawberry mochi inventory", "C", timedelta(days=5)),
    ]
    return [
        {"id": new_quest_id(), "title": title, "rank": rank, "deadline": to_iso(now + delta), "completed": False}
        for title, rank, delta in specs
    ]


def normalize_quest(raw, seen_ids: set) -> dict | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title", "")).strip()
    if not title:
        return None
    rank = str(raw.get("rank", "C")).strip().upper()
    if rank not in RANK_ORDER:
        rank = "C"
    deadline = parse_deadline(raw.get("deadline"))
    if deadline is None:
        deadline = now_local() + timedelta(days=1)
    quest_id = str(raw.get("id") or "").strip() or new_quest_id()
    while quest_id in seen_ids:
        quest_id = new_quest_id()
    seen_ids.add(quest_id)
    return {
        "id": quest_id,
        "title": title,
        "rank": rank,
        "deadline": to_iso(deadline),
        "completed": bool(raw.get("completed", False)),
    }


def load_quests_file() -> tuple[list[dict], str]:
    """Returns (quests, status message). Creates sample quests on first launch."""
    if not QUESTS_FILE.exists():
        quests = sample_quests()
        try:
            atomic_write_json(QUESTS_FILE, quests)
        except OSError as exc:
            return quests, f"✧ couldn't create quests.json ({exc.strerror})"
        return quests, "✿ welcome, adventurer! 5 sample quests posted ♡"
    try:
        data = json.loads(QUESTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = QUESTS_FILE.with_name(f"quests.broken-{stamp}.json")
        try:
            shutil.copy2(QUESTS_FILE, backup)
            return [], f"✧ quests.json was unreadable — backed up as {backup.name}"
        except OSError:
            return [], "✧ quests.json was unreadable"
    if isinstance(data, dict):
        data = data.get("quests", [])
    if not isinstance(data, list):
        data = []
    seen: set = set()
    quests = [quest for quest in (normalize_quest(item, seen) for item in data) if quest]
    active = sum(1 for quest in quests if not quest["completed"])
    return quests, f"✿ synced {active} active quest{'s' if active != 1 else ''} ♡"


def snap_scale(value) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(SCALE_VALUES, key=lambda preset: abs(preset - numeric))


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    source = SETTINGS_FILE if SETTINGS_FILE.exists() else LEGACY_SETTINGS_FILE
    try:
        if source.exists():
            data = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update({key: value for key, value in data.items() if key in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    settings["board_name"] = clean_board_name(settings.get("board_name", DEFAULT_BOARD_NAME))
    if settings["theme"] not in PALETTES:
        settings["theme"] = "berry"
    if settings["sort_key"] not in {key for key, _, _ in SORT_OPTIONS}:
        settings["sort_key"] = "rank"
    if not isinstance(settings["mascot"], int) or not 0 <= settings["mascot"] < len(MASCOTS):
        settings["mascot"] = 0
    settings["scale"] = snap_scale(settings.get("scale", 1.0))
    for key in ("pinned", "sort_asc", "completed_open"):
        settings[key] = bool(settings[key])
    for key in ("x", "y"):
        if not isinstance(settings[key], int):
            settings[key] = None
    return settings


def save_settings(settings: dict) -> None:
    try:
        atomic_write_json(SETTINGS_FILE, settings)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Small widget helpers
# ─────────────────────────────────────────────────────────────────────────────


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_button(text: str, object_name: str, checkable: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(object_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setCheckable(checkable)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return button


def make_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    return label


def make_badge(rank: str, pal: dict, scale: float) -> QLabel:
    colors = pal["badges"][rank]
    badge = QLabel(f"{RANK_GLYPH[rank]} {rank}-Rank")
    badge.setObjectName("RankBadge")
    badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    badge.setStyleSheet(
        "QLabel#RankBadge {"
        f" color: {colors['text']}; background: {colors['bg']};"
        f" border: 1px solid {colors['border']}; border-radius: {px(7, scale, 4)}px;"
        f" padding: {px(1, scale, 1)}px {px(8, scale, 4)}px;"
        f" font-size: {px(10, scale, 6)}px; font-weight: bold; }}"
    )
    if colors["glow"]:
        glow = QGraphicsDropShadowEffect(badge)
        glow.setColor(QColor(colors["glow"]))
        glow.setBlurRadius(px(12, scale, 6))
        glow.setOffset(0, 0)
        badge.setGraphicsEffect(glow)
    return badge


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", object_name: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        if object_name:
            self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._press_pos: QPoint | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            release = event.position().toPoint()
            if (release - self._press_pos).manhattanLength() < 6 and self.rect().contains(release):
                self.clicked.emit()
            self._press_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class HeartButton(QPushButton):
    """( ♡ ) that blooms into a glowing ( ♥ ) on hover / click."""

    def __init__(self, glow_color: str, scale: float, parent: QWidget | None = None):
        super().__init__("( ♡ )", parent)
        self.setObjectName("HeartButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("Clear this quest ♡")
        self._locked = False
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(QColor(glow_color))
        self._glow.setBlurRadius(px(14, scale, 7))
        self._glow.setOffset(0, 0)
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)

    def set_lit(self, lit: bool) -> None:
        self.setText("( ♥ )" if lit else "( ♡ )")
        self.setProperty("lit", lit)
        self._glow.setEnabled(lit)
        repolish(self)

    def lock_lit(self) -> None:
        self._locked = True
        self.setText("( ♥ )")
        self.setProperty("lit", True)
        self._glow.setEnabled(False)
        repolish(self)

    def enterEvent(self, event):
        if not self._locked:
            self.set_lit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._locked:
            self.set_lit(False)
        super().leaveEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  Quest row
# ─────────────────────────────────────────────────────────────────────────────


class QuestRow(QFrame):
    cleared = pyqtSignal(str)
    abandoned = pyqtSignal(str)

    def __init__(self, quest: dict, pal: dict, scale: float, parent: QWidget | None = None):
        super().__init__(parent)
        self.quest_id = quest["id"]
        self.pal = pal
        self.scale = scale
        self.deadline = parse_deadline(quest["deadline"])
        self.clearing = False
        self._armed = False
        self._last_time_state: tuple[str, str] | None = None
        self.anim: QPropertyAnimation | None = None
        self.opacity: QGraphicsOpacityEffect | None = None

        self.setObjectName("QuestRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.content = QWidget()
        self.content.setObjectName("RowContent")
        row = QHBoxLayout(self.content)
        pad_h, pad_v = px(8, scale, 4), px(7, scale, 4)
        row.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        row.setSpacing(px(8, scale, 4))

        self.heart = HeartButton(pal["heart_on"], scale)
        self.heart.clicked.connect(self._on_heart_clicked)
        row.addWidget(self.heart, 0, Qt.AlignmentFlag.AlignVCenter)

        middle = QVBoxLayout()
        middle.setSpacing(px(4, scale, 2))
        self.title_label = QLabel(quest["title"])
        self.title_label.setObjectName("QuestTitle")
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        middle.addWidget(self.title_label)

        meta = QHBoxLayout()
        meta.setSpacing(px(8, scale, 4))
        meta.addWidget(make_badge(quest["rank"], pal, scale))
        self.time_label = make_label("", "QuestTime")
        if self.deadline:
            self.time_label.setToolTip(self.deadline.strftime("due %a %d %b %Y · %H:%M"))
        meta.addWidget(self.time_label)
        meta.addStretch(1)
        middle.addLayout(meta)
        row.addLayout(middle, 1)

        self.abandon_button = make_button("×", "AbandonButton")
        self.abandon_button.setToolTip("Abandon quest (click twice)")
        self.abandon_button.clicked.connect(self._on_abandon_clicked)
        row.addWidget(self.abandon_button, 0, Qt.AlignmentFlag.AlignTop)
        outer_layout.addWidget(self.content)

        self.banner = QLabel(render_banner(pal))
        self.banner.setObjectName("ClearBanner")
        self.banner.setTextFormat(Qt.TextFormat.RichText)
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setVisible(False)
        outer_layout.addWidget(self.banner)

        self._disarm_timer = QTimer(self)
        self._disarm_timer.setSingleShot(True)
        self._disarm_timer.setInterval(ABANDON_CONFIRM_MS)
        self._disarm_timer.timeout.connect(self._disarm)

    def update_time(self, now: datetime, pulse: bool) -> None:
        if self.clearing:
            return
        if self.deadline is None:
            state = ("⋆ no deadline", self.pal["muted"])
        else:
            state = describe_remaining(self.deadline, now, self.pal, pulse)
        if state != self._last_time_state:
            self._last_time_state = state
            self.time_label.setText(state[0])
            self.time_label.setStyleSheet(
                f"QLabel#QuestTime {{ color: {state[1]}; font-size: {px(10, self.scale, 6)}px; font-weight: bold; }}"
            )

    def _on_heart_clicked(self) -> None:
        if self.clearing:
            return
        self.clearing = True
        self._disarm_timer.stop()
        row_height = max(self.height(), px(46, self.scale, 28))
        self.heart.lock_lit()
        self.heart.setEnabled(False)
        self.abandon_button.setEnabled(False)
        self.content.setVisible(False)
        self.banner.setFixedHeight(row_height)
        self.banner.setVisible(True)

        self.opacity = QGraphicsOpacityEffect(self)
        self.opacity.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity)

        self.anim = QPropertyAnimation(self.opacity, b"opacity", self)
        self.anim.setDuration(CLEAR_FADE_MS)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self.anim.finished.connect(self._on_fade_finished)
        self.anim.start()

    def _on_fade_finished(self) -> None:
        self.cleared.emit(self.quest_id)

    def stop_animation(self) -> None:
        if self.anim is not None:
            try:
                self.anim.finished.disconnect(self._on_fade_finished)
            except TypeError:
                pass
            self.anim.stop()

    def _on_abandon_clicked(self) -> None:
        if self.clearing:
            return
        if self._armed:
            self._disarm_timer.stop()
            self.abandoned.emit(self.quest_id)
            return
        self._armed = True
        self.abandon_button.setText("× sure?")
        self.abandon_button.setProperty("armed", True)
        repolish(self.abandon_button)
        self._disarm_timer.start()

    def _disarm(self) -> None:
        self._armed = False
        self.abandon_button.setText("×")
        self.abandon_button.setProperty("armed", False)
        repolish(self.abandon_button)


# ─────────────────────────────────────────────────────────────────────────────
#  The board
# ─────────────────────────────────────────────────────────────────────────────


class SmugGuildBoard(QWidget):
    def __init__(self, autostart_launch: bool = False):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnBottomHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.autostart_launch = autostart_launch
        self.settings = load_settings()
        self.scale: float = self.settings["scale"]
        self.pal = PALETTES[self.settings["theme"]]
        self.composited = is_x11_composited()
        self.quests: list[dict] = []
        self.rows: dict[str, QuestRow] = {}
        self.drag_offset: QPoint | None = None
        self.tick_count = 0
        self.cheering = False
        self.spin_index = 0
        self._x11_hints_applied = False
        self._ready = False
        self._applying_pos = False

        # Migrate legacy autostart desktop entry cleanly on startup if present
        if _autostart_entry_active(LEGACY_AUTOSTART_FILE) and not AUTOSTART_FILE.exists():
            set_autorun_enabled(True, self.board_name)

        self._build_ui()
        self._install_scale_shortcuts()

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.tick)

        self.spin_timer = QTimer(self)
        self.spin_timer.setInterval(RESYNC_MS // len(SPIN_FRAMES))
        self.spin_timer.timeout.connect(self._spin_step)

        self.cheer_timer = QTimer(self)
        self.cheer_timer.setSingleShot(True)
        self.cheer_timer.setInterval(CHEER_HOLD_MS)
        self.cheer_timer.timeout.connect(lambda: self.set_cheering(False))

        self.move_save_timer = QTimer(self)
        self.move_save_timer.setSingleShot(True)
        self.move_save_timer.setInterval(250)
        self.move_save_timer.timeout.connect(self._persist_current_pos)

        self.quests, message = load_quests_file()
        self.update_board_title()
        self.apply_scale_and_theme()
        self.update_pin_button()
        self.update_sort_buttons()
        self.completed_box.setVisible(self.settings["completed_open"])
        self.set_status(message)
        self.restore_position()
        self.tick()
        self.tick_timer.start()

    # ── Computed scaled geometry & board name ────────────────────────────────
    @property
    def board_name(self) -> str:
        return clean_board_name(self.settings.get("board_name", DEFAULT_BOARD_NAME))

    @property
    def board_width(self) -> int:
        return px(BASE_BOARD_WIDTH, self.scale, 220)

    @property
    def corner_radius(self) -> int:
        return px(BASE_CORNER_RADIUS, self.scale, 10)

    @property
    def content_width(self) -> int:
        return self.board_width - 2 * px(BASE_MARGIN_L, self.scale, 10)

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)

        # Header (drag handle)
        self.header = QWidget()
        self.header.setObjectName("Header")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)

        self.mascot = ClickableLabel(object_name="Mascot")
        self.mascot.setTextFormat(Qt.TextFormat.RichText)
        self.mascot.setToolTip("click me ~ ♡")
        self.mascot.clicked.connect(self.cycle_mascot)
        self.header_layout.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.titles_layout = QVBoxLayout()
        self.titles_layout.addStretch(1)
        self.board_title_label = ClickableLabel(object_name="BoardTitle")
        self.board_title_label.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.board_title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.board_title_label.setWordWrap(True)
        self.board_title_label.setToolTip("Click to rename board ~ ✧")
        self.board_title_label.clicked.connect(lambda: self.toggle_rename_box())
        self.titles_layout.addWidget(self.board_title_label)
        self.subtitle_label = make_label("", "BoardSubtitle")
        self.titles_layout.addWidget(self.subtitle_label)
        self.clock_label = make_label("", "BoardClock")
        self.titles_layout.addWidget(self.clock_label)
        self.titles_layout.addStretch(1)
        self.header_layout.addLayout(self.titles_layout, 1)

        self.right_layout = QVBoxLayout()
        self.pin_button = make_button("", "PillButton")
        self.pin_button.clicked.connect(lambda: self.toggle_pin())
        self.right_layout.addWidget(self.pin_button, 0, Qt.AlignmentFlag.AlignRight)

        self.style_pills_row = QHBoxLayout()
        self.theme_button = make_button("", "PillButton")
        self.theme_button.setToolTip("Switch Berry / Cream glass")
        self.theme_button.clicked.connect(lambda: self.toggle_theme())
        self.scale_button = make_button("", "PillButton")
        self.scale_button.setToolTip("Click to scale board · Right-click for all sizes")
        self.scale_button.clicked.connect(lambda: self.cycle_scale_down())
        self.style_pills_row.addStretch(1)
        self.style_pills_row.addWidget(self.theme_button)
        self.style_pills_row.addWidget(self.scale_button)
        self.right_layout.addLayout(self.style_pills_row)

        self.resync_button = make_button(RESYNC_IDLE_TEXT, "ResyncButton")
        self.resync_button.setToolTip("Reload quests.json from disk")
        self.resync_button.clicked.connect(lambda: self.start_resync())
        self.right_layout.addWidget(self.resync_button, 0, Qt.AlignmentFlag.AlignRight)
        self.right_layout.addStretch(1)
        self.header_layout.addLayout(self.right_layout)
        self.root_layout.addWidget(self.header)

        # Inline board name editor (hidden by default; opened by clicking title or via sidemenu)
        self.root_layout.addWidget(self._build_rename_box())

        # Sparkle divider
        self.divider_layout = QHBoxLayout()
        for index in range(2):
            line = QFrame()
            line.setObjectName("DividerLine")
            line.setFixedHeight(1)
            self.divider_layout.addWidget(line, 1, Qt.AlignmentFlag.AlignVCenter)
            if index == 0:
                self.divider_layout.addWidget(make_label("⋆ ˚ ✿ ˚ ⋆", "DividerGlyph"))
        self.root_layout.addLayout(self.divider_layout)

        # Sort pills + new quest button
        self.sort_row = QHBoxLayout()
        self.sort_buttons: dict[str, QPushButton] = {}
        for key, _name, _glyph in SORT_OPTIONS:
            button = make_button("", "SortPill")
            button.setToolTip("Sort · click again to flip order")
            button.clicked.connect(lambda _checked=False, k=key: self.on_sort_clicked(k))
            self.sort_buttons[key] = button
            self.sort_row.addWidget(button)
        self.sort_row.addStretch(1)
        self.new_quest_button = make_button(NEW_QUEST_TEXT, "NewQuestButton")
        self.new_quest_button.clicked.connect(lambda: self.toggle_creator())
        self.sort_row.addWidget(self.new_quest_button)
        self.root_layout.addLayout(self.sort_row)

        # Quest creator (hidden by default)
        self.root_layout.addWidget(self._build_creator())

        # Active quest list
        self.scroll = QScrollArea()
        self.scroll.setObjectName("QuestScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.list_container = QWidget()
        self.list_container.setObjectName("ListContainer")
        self.list_container.setAutoFillBackground(False)
        self.list_layout = QVBoxLayout(self.list_container)
        self.scroll.setWidget(self.list_container)
        self.root_layout.addWidget(self.scroll)

        self.empty_label = make_label("✿ no active quests ~ time for tea and mochi ♡", "EmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        self.root_layout.addWidget(self.empty_label)

        # Completed footer
        self.completed_toggle = make_button("", "CompletedToggle")
        self.completed_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.completed_toggle.clicked.connect(lambda: self.toggle_completed())
        self.root_layout.addWidget(self.completed_toggle)

        self.completed_box = QFrame()
        self.completed_box.setObjectName("CompletedBox")
        self.completed_box_layout = QVBoxLayout(self.completed_box)
        self.completed_scroll = QScrollArea()
        self.completed_scroll.setWidgetResizable(True)
        self.completed_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.completed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.completed_scroll.viewport().setAutoFillBackground(False)
        self.completed_list = QWidget()
        self.completed_list.setObjectName("CompletedList")
        self.completed_list_layout = QVBoxLayout(self.completed_list)
        self.completed_scroll.setWidget(self.completed_list)
        self.completed_box_layout.addWidget(self.completed_scroll)
        self.clear_history_button = make_button("[ Clear History ✧ ]", "ClearHistoryButton")
        self.clear_history_button.clicked.connect(lambda: self.clear_history())
        self.completed_box_layout.addWidget(self.clear_history_button, 0, Qt.AlignmentFlag.AlignRight)
        self.root_layout.addWidget(self.completed_box)

        # Status & copyright footer
        self.footer_layout = QVBoxLayout()
        self.status_label = make_label("", "StatusLabel")
        self.status_label.setWordWrap(True)
        self.credit_label = make_label(APP_CREDIT, "CreditLabel")
        self.credit_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.footer_layout.addWidget(self.status_label)
        self.footer_layout.addWidget(self.credit_label)
        self.root_layout.addLayout(self.footer_layout)

    def _build_rename_box(self) -> QFrame:
        self.rename_box = QFrame()
        self.rename_box.setObjectName("RenameBox")
        self.rename_box.setVisible(False)
        self.rename_layout = QVBoxLayout(self.rename_box)

        self.rename_layout.addWidget(make_label("✧ customize board display name ~", "FieldLabel"))
        self.board_name_input = QLineEdit()
        self.board_name_input.setPlaceholderText(f"✧ {DEFAULT_BOARD_NAME}")
        self.board_name_input.setMaxLength(MAX_BOARD_NAME_LEN)
        self.board_name_input.returnPressed.connect(self.submit_board_name)
        self.rename_layout.addWidget(self.board_name_input)

        self.rename_buttons = QHBoxLayout()
        reset_btn = make_button("[ Default ✿ ]", "CancelButton")
        reset_btn.setToolTip(f"Reset to {DEFAULT_BOARD_NAME}")
        reset_btn.clicked.connect(self.reset_board_name)
        self.rename_buttons.addWidget(reset_btn)
        self.rename_buttons.addStretch(1)
        cancel_btn = make_button("[ Cancel ✧ ]", "CancelButton")
        cancel_btn.clicked.connect(lambda: self.toggle_rename_box(False))
        save_btn = make_button("[ Save ♡ ]", "AcceptButton")
        save_btn.clicked.connect(self.submit_board_name)
        self.rename_buttons.addWidget(cancel_btn)
        self.rename_buttons.addWidget(save_btn)
        self.rename_layout.addLayout(self.rename_buttons)

        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.rename_box)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(lambda: self.toggle_rename_box(False))
        return self.rename_box

    def _build_creator(self) -> QFrame:
        self.creator = QFrame()
        self.creator.setObjectName("Creator")
        self.creator.setVisible(False)
        self.creator_layout = QVBoxLayout(self.creator)

        self.creator_layout.addWidget(make_label("♡ post a new quest ~", "FieldLabel"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("✧ name your quest…")
        self.title_input.setMaxLength(140)
        self.title_input.returnPressed.connect(self.submit_new_quest)
        self.title_input.textEdited.connect(lambda _text: self._clear_creator_errors())
        self.creator_layout.addWidget(self.title_input)

        self.rank_row = QHBoxLayout()
        self.rank_label = make_label("rank", "FieldLabel")
        self.rank_row.addWidget(self.rank_label)
        self.rank_group = QButtonGroup(self)
        self.rank_group.setExclusive(True)
        for rank in RANKS:
            button = make_button(f"{RANK_GLYPH[rank]} {rank}", "ChoicePill", checkable=True)
            button.setProperty("rank_value", rank)
            button.setChecked(rank == DEFAULT_RANK)
            self.rank_group.addButton(button)
            self.rank_row.addWidget(button)
        self.rank_row.addStretch(1)
        self.creator_layout.addLayout(self.rank_row)

        self.due_row = QHBoxLayout()
        self.due_label = make_label("due", "FieldLabel")
        self.due_row.addWidget(self.due_label)
        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        for text, delta in DEADLINE_PRESETS:
            button = make_button(text, "ChoicePill", checkable=True)
            button.setProperty("preset_seconds", int(delta.total_seconds()))
            button.setChecked(text == DEFAULT_PRESET)
            button.clicked.connect(lambda _checked=False: self.custom_input.clear())
            self.preset_group.addButton(button)
            self.due_row.addWidget(button)
        self.due_row.addStretch(1)
        self.creator_layout.addLayout(self.due_row)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("or custom deadline:  YYYY-MM-DD HH:MM")
        self.custom_input.setMaxLength(16)
        self.custom_input.returnPressed.connect(self.submit_new_quest)
        self.custom_input.textEdited.connect(lambda _text: self._clear_creator_errors())
        self.creator_layout.addWidget(self.custom_input)

        self.creator_hint = make_label("", "Hint")
        self.creator_hint.setVisible(False)
        self.creator_hint.setWordWrap(True)
        self.creator_layout.addWidget(self.creator_hint)

        self.creator_buttons = QHBoxLayout()
        self.creator_buttons.addStretch(1)
        cancel = make_button("[ Cancel ✧ ]", "CancelButton")
        cancel.clicked.connect(lambda: self.toggle_creator(False))
        accept = make_button("[ Accept Quest ♡ ]", "AcceptButton")
        accept.clicked.connect(lambda: self.submit_new_quest())
        self.creator_buttons.addWidget(cancel)
        self.creator_buttons.addWidget(accept)
        self.creator_layout.addLayout(self.creator_buttons)

        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.creator)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(lambda: self.toggle_creator(False))
        return self.creator

    def _install_scale_shortcuts(self) -> None:
        for seq, fn in (
            ("Ctrl+-", self.step_scale_smaller),
            ("Ctrl+_", self.step_scale_smaller),
            ("Ctrl+=", self.step_scale_larger),
            ("Ctrl++", self.step_scale_larger),
            ("Ctrl+0", lambda: self.set_scale(1.0)),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(fn)

    def _apply_scaled_spacings(self) -> None:
        s = self.scale
        self.setFixedWidth(self.board_width)
        self.root_layout.setContentsMargins(
            px(BASE_MARGIN_L, s, 10),
            px(BASE_MARGIN_T, s, 9),
            px(BASE_MARGIN_R, s, 10),
            px(BASE_MARGIN_B, s, 8),
        )
        self.root_layout.setSpacing(px(8, s, 4))
        self.header_layout.setSpacing(px(10, s, 5))
        self.titles_layout.setSpacing(px(2, s, 1))
        self.right_layout.setSpacing(px(4, s, 2))
        self.style_pills_row.setSpacing(px(4, s, 2))
        self.divider_layout.setSpacing(px(8, s, 4))
        self.sort_row.setSpacing(px(5, s, 2))
        self.list_layout.setContentsMargins(0, 0, px(4, s, 2), 0)
        self.list_layout.setSpacing(px(6, s, 3))
        self.completed_box_layout.setContentsMargins(px(10, s, 5), px(8, s, 4), px(10, s, 5), px(8, s, 4))
        self.completed_box_layout.setSpacing(px(6, s, 3))
        self.completed_list_layout.setContentsMargins(0, 0, px(4, s, 2), 0)
        self.completed_list_layout.setSpacing(px(3, s, 2))
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(px(2, s, 1))

        cpad = px(10, s, 5)
        self.rename_layout.setContentsMargins(cpad, cpad, cpad, cpad)
        self.rename_layout.setSpacing(px(6, s, 3))
        self.rename_buttons.setSpacing(px(5, s, 2))

        self.creator_layout.setContentsMargins(cpad, cpad, cpad, cpad)
        self.creator_layout.setSpacing(px(7, s, 4))
        self.rank_row.setSpacing(px(5, s, 2))
        self.due_row.setSpacing(px(5, s, 2))
        self.creator_buttons.setSpacing(px(6, s, 3))
        label_w = px(34, s, 20)
        self.rank_label.setFixedWidth(label_w)
        self.due_label.setFixedWidth(label_w)

    # ── Board display name customization ─────────────────────────────────────
    def update_board_title(self) -> None:
        name = self.board_name
        self.setWindowTitle(name)
        self.board_title_label.setText(f"✧ {name} ✧")

    def toggle_rename_box(self, show: bool | None = None) -> None:
        if show is None:
            show = not self.rename_box.isVisible()
        self.rename_box.setVisible(show)
        if show:
            self.board_name_input.setText(self.board_name)
            self.activateWindow()
            self.board_name_input.setFocus(Qt.FocusReason.OtherFocusReason)
            self.board_name_input.selectAll()
        self.schedule_relayout()

    def set_board_name(self, raw_name: str) -> None:
        new_name = clean_board_name(raw_name)
        self.settings["board_name"] = new_name
        save_settings(self.settings)
        self.update_board_title()
        if is_autorun_enabled():
            set_autorun_enabled(True, new_name)
        self.set_status(f"✧ board renamed to “{new_name}”")
        self.schedule_relayout()

    def submit_board_name(self) -> None:
        entered = self.board_name_input.text()
        self.toggle_rename_box(False)
        self.set_board_name(entered)

    def reset_board_name(self) -> None:
        self.toggle_rename_box(False)
        self.set_board_name(DEFAULT_BOARD_NAME)

    # ── Painting: frosted glass panel, borders, corner sparkles ──────────────
    def _update_window_shape(self) -> None:
        if self.composited:
            self.clearMask()
            return
        if self.width() <= 0 or self.height() <= 0:
            return
        rad = self.corner_radius
        bitmap = QBitmap(self.size())
        bitmap.fill(Qt.GlobalColor.color0)
        mask_painter = QPainter(bitmap)
        mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        mask_painter.setPen(Qt.GlobalColor.color1)
        mask_painter.setBrush(Qt.GlobalColor.color1)
        mask_painter.drawRoundedRect(self.rect(), rad, rad)
        mask_painter.end()
        self.setMask(bitmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_window_shape()

    def paintEvent(self, event):
        s = self.scale
        rad = self.corner_radius
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        outer = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(outer, rad, rad)
        r, g, b, a = self.pal["bg"]
        painter.fillPath(path, QColor(r, g, b, a if self.composited else 255))
        painter.setPen(QPen(QColor(self.pal["border"]), max(1.5, 2.0 * s)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        inset = max(3.5, 5.0 * s)
        inner_rad = max(6.0, rad - inset)
        glow = QColor(self.pal["inner"])
        glow.setAlpha(self.pal["inner_alpha"])
        painter.setPen(QPen(glow, 1))
        painter.drawRoundedRect(outer.adjusted(inset, inset, -inset, -inset), inner_rad, inner_rad)

        spark_fs = px(11, s, 7)
        font = QFont("DejaVu Sans")
        font.setPixelSize(spark_fs)
        painter.setFont(font)
        painter.setPen(QColor(self.pal["sparkle"]))
        width, height = self.width(), self.height()
        lx = px(8, s, 5)
        rx = width - px(17, s, 11)
        ty = px(17, s, 11)
        by = height - px(7, s, 4)
        for x, y in ((lx, ty), (rx, ty), (lx, by), (rx, by)):
            painter.drawText(QPointF(x, y), "✧")
        painter.end()

    # ── Scale & Theme ────────────────────────────────────────────────────────
    def apply_scale_and_theme(self) -> None:
        self.scale = self.settings["scale"]
        self.pal = PALETTES[self.settings["theme"]]
        self._apply_scaled_spacings()
        self.setStyleSheet(build_stylesheet(self.pal, self.scale))
        self.update_board_title()
        if self.scale < 0.75:
            self.theme_button.setText("( ✦ )" if self.settings["theme"] == "berry" else "( ✿ )")
        else:
            self.theme_button.setText("( Berry ✦ )" if self.settings["theme"] == "berry" else "( Cream ✿ )")
        self.scale_button.setText(f"( {int(round(self.scale * 100))}% ⋆ )")
        self.resync_button.setMinimumWidth(0)
        self.resync_button.setMaximumWidth(16777215)
        self.resync_button.setText(RESYNC_IDLE_TEXT)
        self.render_mascot()
        self.rebuild_lists()
        self.resync_button.setFixedWidth(self.resync_button.sizeHint().width() + px(8, self.scale, 4))
        self.update()

    def set_scale(self, new_scale: float) -> None:
        snapped = snap_scale(new_scale)
        if abs(snapped - self.settings["scale"]) < 1e-4:
            return
        self.settings["scale"] = snapped
        save_settings(self.settings)
        self.apply_scale_and_theme()
        self._clamp_on_screen_if_unpinned()
        self.set_status(f"⋆ board scale: {int(round(snapped * 100))}%")

    def cycle_scale_down(self) -> None:
        """Click the size pill to step down through presets (wrapping around)."""
        idx = SCALE_VALUES.index(snap_scale(self.settings["scale"]))
        next_idx = (idx - 1) % len(SCALE_VALUES)
        self.set_scale(SCALE_VALUES[next_idx])

    def step_scale_smaller(self) -> None:
        idx = SCALE_VALUES.index(snap_scale(self.settings["scale"]))
        if idx > 0:
            self.set_scale(SCALE_VALUES[idx - 1])

    def step_scale_larger(self) -> None:
        idx = SCALE_VALUES.index(snap_scale(self.settings["scale"]))
        if idx + 1 < len(SCALE_VALUES):
            self.set_scale(SCALE_VALUES[idx + 1])

    def toggle_theme(self) -> None:
        self.settings["theme"] = "cream" if self.settings["theme"] == "berry" else "berry"
        save_settings(self.settings)
        self.apply_scale_and_theme()
        self.set_status("✿ theme: sakura cream" if self.settings["theme"] == "cream" else "✦ theme: berry glass")

    # ── Mascot ───────────────────────────────────────────────────────────────
    def render_mascot(self) -> None:
        mascot = MASCOTS[self.settings["mascot"]]
        lines = mascot["cheer"] if self.cheering else mascot["normal"]
        self.mascot.setText(render_mascot(lines, self.pal, self.scale))

    def cycle_mascot(self) -> None:
        self.settings["mascot"] = (self.settings["mascot"] + 1) % len(MASCOTS)
        save_settings(self.settings)
        self.render_mascot()
        self.set_status(f"♡ mascot: {MASCOTS[self.settings['mascot']]['name']}")
        self.schedule_relayout()

    def set_cheering(self, cheering: bool) -> None:
        self.cheering = cheering
        self.render_mascot()

    # ── Pin, drag & persistent position ──────────────────────────────────────
    def update_pin_button(self) -> None:
        pinned = self.settings["pinned"]
        self.pin_button.setText("( Pin: On ♡ )" if pinned else "( Pin: Off ✧ )")
        self.pin_button.setProperty("active", pinned)
        if pinned and self.settings["x"] is not None and self.settings["y"] is not None:
            self.pin_button.setToolTip(f"Pinned at ({self.settings['x']}, {self.settings['y']}) · click to unlock")
        else:
            self.pin_button.setToolTip("Drag the header to move, then click to pin")
        repolish(self.pin_button)
        self.header.setCursor(Qt.CursorShape.ArrowCursor if pinned else Qt.CursorShape.OpenHandCursor)

    def toggle_pin(self) -> None:
        self.settings["pinned"] = not self.settings["pinned"]
        self._persist_current_pos()
        self.update_pin_button()
        if self.settings["pinned"]:
            self.set_status(f"♡ pinned at ({self.settings['x']}, {self.settings['y']}) — position saved")
        else:
            self.set_status("✧ unpinned — drag the header to reposition")

    def _safe_move(self, x: int, y: int) -> None:
        self._applying_pos = True
        try:
            self.move(x, y)
        finally:
            self._applying_pos = False

    def _persist_current_pos(self) -> None:
        pos = self.pos()
        self.settings["x"], self.settings["y"] = int(pos.x()), int(pos.y())
        save_settings(self.settings)

    def _enforce_pinned_pos(self) -> None:
        if not self.settings["pinned"]:
            return
        tx, ty = self.settings["x"], self.settings["y"]
        if tx is not None and ty is not None and (self.x() != tx or self.y() != ty):
            self._safe_move(tx, ty)

    def _clamp_on_screen_if_unpinned(self) -> None:
        if self.settings["pinned"]:
            return
        screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        nx = max(area.left(), min(self.x(), area.right() - self.board_width))
        ny = max(area.top(), min(self.y(), area.bottom() - 80))
        if nx != self.x() or ny != self.y():
            self._safe_move(nx, ny)
            self._persist_current_pos()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self._ready or self._applying_pos:
            return
        if self.settings["pinned"]:
            tx, ty = self.settings["x"], self.settings["y"]
            if tx is not None and ty is not None and (self.x() != tx or self.y() != ty):
                QTimer.singleShot(0, self._enforce_pinned_pos)
            return
        if self.drag_offset is None:
            self.move_save_timer.start()

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self.settings["pinned"]
            and self.header.geometry().contains(event.position().toPoint())
        ):
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.header.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            target = event.globalPosition().toPoint() - self.drag_offset
            self._safe_move(target.x(), target.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_offset is not None and event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = None
            self._persist_current_pos()
            self.update_pin_button()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def restore_position(self) -> None:
        x, y = self.settings["x"], self.settings["y"]
        if x is not None and y is not None:
            probe = QPoint(x + min(40, self.board_width // 2), y + 20)
            screen = QGuiApplication.screenAt(probe) or QGuiApplication.primaryScreen()
            if screen is not None:
                mon = screen.geometry()
                cx = max(mon.left() - self.board_width + 60, min(x, mon.right() - 40))
                cy = max(mon.top() - 10, min(y, mon.bottom() - 40))
                self._safe_move(cx, cy)
                return
            self._safe_move(x, y)
            return
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self._safe_move(max(area.left(), area.right() - self.board_width - 28), area.top() + 28)

    # ── Sidemenu (right-click context menu) ──────────────────────────────────
    def toggle_autorun(self) -> None:
        currently_on = is_autorun_enabled()
        _ok, message = set_autorun_enabled(not currently_on, self.board_name)
        self.set_status(message)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        act_resync = menu.addAction("↻  Resync quests")
        act_resync.triggered.connect(lambda _c=False: self.start_resync())

        act_new = menu.addAction("♡  New quest")
        act_new.triggered.connect(lambda _c=False: self.toggle_creator(True))

        act_rename = menu.addAction("✦  Rename board…")
        act_rename.triggered.connect(lambda _c=False: self.toggle_rename_box(True))

        act_theme = menu.addAction("✿  Switch theme (Berry / Cream)")
        act_theme.triggered.connect(lambda _c=False: self.toggle_theme())

        # Board Size submenu
        size_menu = menu.addMenu("⋆  Board Size")
        size_group = QActionGroup(size_menu)
        size_group.setExclusive(True)
        current_scale = snap_scale(self.settings["scale"])
        for val, label in SCALE_PRESETS:
            act = size_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(abs(val - current_scale) < 1e-4)
            act.triggered.connect(lambda _c=False, v=val: self.set_scale(v))
            size_group.addAction(act)
        size_menu.addSeparator()
        act_smaller = size_menu.addAction("−  Smaller  (Ctrl+-)")
        act_smaller.setEnabled(current_scale > SCALE_VALUES[0] + 1e-4)
        act_smaller.triggered.connect(lambda _c=False: self.step_scale_smaller())
        act_larger = size_menu.addAction("+  Larger   (Ctrl++)")
        act_larger.setEnabled(current_scale < SCALE_VALUES[-1] - 1e-4)
        act_larger.triggered.connect(lambda _c=False: self.step_scale_larger())

        menu.addSeparator()

        # Pin toggle (remembers position)
        pin_label = (
            f"♥  Pin position ({self.settings['x']}, {self.settings['y']})"
            if self.settings["pinned"] and self.settings["x"] is not None
            else "✧  Pin position"
        )
        act_pin = menu.addAction(pin_label)
        act_pin.setCheckable(True)
        act_pin.setChecked(self.settings["pinned"])
        act_pin.triggered.connect(lambda _c=False: self.toggle_pin())

        # Autorun at boot toggle
        autorun_on = is_autorun_enabled()
        act_autorun = menu.addAction("♥  Autorun at boot" if autorun_on else "♡  Autorun at boot")
        act_autorun.setCheckable(True)
        act_autorun.setChecked(autorun_on)
        act_autorun.triggered.connect(lambda _c=False: self.toggle_autorun())

        menu.addSeparator()
        act_quit = menu.addAction("×  Close board")
        act_quit.triggered.connect(QApplication.quit)

        menu.exec(event.globalPos())

    # ── Sorting ──────────────────────────────────────────────────────────────
    def on_sort_clicked(self, key: str) -> None:
        if self.settings["sort_key"] == key:\
            self.settings["sort_asc"] = not self.settings["sort_asc"]
        else:
            self.settings["sort_key"] = key
            self.settings["sort_asc"] = True
        save_settings(self.settings)
        self.update_sort_buttons()
        self.rebuild_active_list()
        self.schedule_relayout()

    def update_sort_buttons(self) -> None:
        arrow = "▾" if self.settings["sort_asc"] else "▴"
        for key, name, glyph in SORT_OPTIONS:
            button = self.sort_buttons[key]
            active = key == self.settings["sort_key"]
            button.setText(f"( {arrow} {name} {glyph} )" if active else f"( {name} {glyph} )")
            button.setProperty("active", active)
            repolish(button)

    def sorted_active_quests(self) -> list[dict]:
        active = [quest for quest in self.quests if not quest["completed"]]
        ascending = self.settings["sort_asc"]

        def deadline_of(quest: dict) -> datetime:
            return parse_deadline(quest["deadline"]) or datetime.max

        key = self.settings["sort_key"]
        if key == "rank":
            return sorted(
                active,
                key=lambda q: (
                    RANK_ORDER[q["rank"]] if ascending else -RANK_ORDER[q["rank"]],
                    deadline_of(q),
                    q["title"].casefold(),
                ),
            )
        if key == "time":
            by_rank = sorted(active, key=lambda q: (RANK_ORDER[q["rank"]], q["title"].casefold()))
            return sorted(by_rank, key=deadline_of, reverse=not ascending)
        by_deadline = sorted(active, key=deadline_of)
        return sorted(by_deadline, key=lambda q: q["title"].casefold(), reverse=not ascending)

    # ── List building ────────────────────────────────────────────────────────
    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _flush_pending_clears(self) -> None:
        changed = False
        for quest_id, row in self.rows.items():
            if row.clearing:
                row.stop_animation()
                quest = self.find_quest(quest_id)
                if quest is not None and not quest["completed"]:
                    quest["completed"] = True
                    changed = True
        if changed:
            self.save_quests()

    def rebuild_lists(self) -> None:
        self.rebuild_active_list()
        self.rebuild_completed_list()
        self.schedule_relayout()

    def rebuild_active_list(self) -> None:
        self._flush_pending_clears()
        self._clear_layout(self.list_layout)
        self.rows = {}
        quests = self.sorted_active_quests()
        for quest in quests:
            row = QuestRow(quest, self.pal, self.scale, self.list_container)
            row.cleared.connect(self.on_quest_cleared)
            row.abandoned.connect(self.on_quest_abandoned)
            self.list_layout.addWidget(row)
            self.rows[quest["id"]] = row
        self.list_layout.addStretch(1)
        self.scroll.setVisible(bool(quests))
        self.empty_label.setVisible(not quests)
        self.update_counts()
        self.refresh_row_times()

    def rebuild_completed_list(self) -> None:
        self._clear_layout(self.completed_list_layout)
        done = sorted(
            (quest for quest in self.quests if quest["completed"]),
            key=lambda q: (RANK_ORDER[q["rank"]], q["title"].casefold()),
        )
        if not done:
            self.completed_list_layout.addWidget(make_label("⋆ nothing cleared yet ~ you've got this ♡", "CompletedItem"))
        for quest in done:
            label = make_label("", "CompletedItem")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.setText(f"♥ {RANK_GLYPH[quest['rank']]} <s>{html.escape(quest['title'])}</s>")
            self.completed_list_layout.addWidget(label)
        self.completed_list_layout.addStretch(1)
        self.clear_history_button.setEnabled(bool(done))
        self.update_completed_toggle()
        self.update_counts()

    def update_completed_toggle(self) -> None:
        count = sum(1 for quest in self.quests if quest["completed"])
        arrow = "▾" if self.settings["completed_open"] else "▸"
        self.completed_toggle.setText(f"✿ Completed Quests ({count})  {arrow}")

    def update_counts(self) -> None:
        active = sum(1 for quest in self.quests if not quest["completed"])
        done = len(self.quests) - active
        self.subtitle_label.setText(f"♡ {active} active quest{'s' if active != 1 else ''} · ✿ {done} cleared")

    def toggle_completed(self) -> None:
        self.settings["completed_open"] = not self.settings["completed_open"]
        save_settings(self.settings)
        self.completed_box.setVisible(self.settings["completed_open"])
        self.update_completed_toggle()
        self.schedule_relayout()

    # ── Layout fitting (window grows/shrinks with its content & scale) ───────
    def schedule_relayout(self) -> None:
        QTimer.singleShot(0, self._relayout)

    @staticmethod
    def _fit_scroll(scroll: QScrollArea, inner: QWidget, max_height: int, width: int, pad: int) -> None:
        lay = inner.layout()
        lay.activate()
        height = (lay.totalHeightForWidth(width) + pad) if lay.hasHeightForWidth() else lay.totalSizeHint().height()
        scroll.setFixedHeight(max(1, min(height, max_height)))

    def _relayout(self) -> None:
        s = self.scale
        cw = self.content_width
        list_max = px(BASE_LIST_MAX_HEIGHT, s, 180)
        comp_max = px(BASE_COMPLETED_MAX_HEIGHT, s, 70)
        self._fit_scroll(self.scroll, self.list_container, list_max, cw - px(6, s, 3), px(6, s, 4))
        self._fit_scroll(self.completed_scroll, self.completed_list, comp_max, cw - px(24, s, 12), px(6, s, 4))
        layout = self.layout()
        layout.invalidate()
        layout.activate()
        self.resize(self.board_width, max(self.sizeHint().height(), self.minimumSizeHint().height()))
        self.update()

    # ── Timers ───────────────────────────────────────────────────────────────
    def tick(self) -> None:
        self.tick_count += 1
        if self.tick_count % 5 == 0:
            composited = is_x11_composited()
            if composited != self.composited:
                self.composited = composited
                self._update_window_shape()
                self.update()
        self.refresh_row_times()
        self.clock_label.setText(now_local().strftime("⋆ %a %d %b · %H:%M:%S"))

    def refresh_row_times(self) -> None:
        now = now_local()
        pulse = self.tick_count % 2 == 1
        for row in self.rows.values():
            row.update_time(now, pulse)

    # ── Resync ───────────────────────────────────────────────────────────────
    def start_resync(self) -> None:
        if self.spin_timer.isActive():
            return
        self.spin_index = 0
        self.cheer_timer.stop()
        self.set_cheering(True)
        self._flush_pending_clears()
        self.quests, message = load_quests_file()
        self.rebuild_lists()
        self.set_status(message)
        self._spin_step()
        self.spin_timer.start()

    def _spin_step(self) -> None:
        if self.spin_index >= len(SPIN_FRAMES):
            self.spin_timer.stop()
            self.resync_button.setText(RESYNC_IDLE_TEXT)
            self.cheer_timer.start()
            return
        self.resync_button.setText(f"[ {SPIN_FRAMES[self.spin_index]} Resync ✿ ]")
        self.spin_index += 1

    # ── Quest mutations ──────────────────────────────────────────────────────
    def find_quest(self, quest_id: str) -> dict | None:
        return next((quest for quest in self.quests if quest["id"] == quest_id), None)

    def save_quests(self) -> None:
        try:
            atomic_write_json(QUESTS_FILE, self.quests)
        except OSError as exc:
            self.set_status(f"✧ couldn't save quests.json ({exc.strerror})")

    def _remove_row(self, quest_id: str) -> None:
        row = self.rows.pop(quest_id, None)
        if row is not None:
            self.list_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        has_rows = bool(self.rows)
        self.scroll.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

    def on_quest_cleared(self, quest_id: str) -> None:
        quest = self.find_quest(quest_id)
        if quest is not None:
            quest["completed"] = True
            self.save_quests()
            self.set_status(f"♥ quest clear! “{quest['title']}”")
        self._remove_row(quest_id)
        self.rebuild_completed_list()
        self.schedule_relayout()

    def on_quest_abandoned(self, quest_id: str) -> None:
        quest = self.find_quest(quest_id)
        if quest is not None:
            self.quests.remove(quest)
            self.save_quests()
            self.set_status(f"✧ quest abandoned: “{quest['title']}”")
        self._remove_row(quest_id)
        self.update_counts()
        self.schedule_relayout()

    def clear_history(self) -> None:
        count = sum(1 for quest in self.quests if quest["completed"])
        if not count:
            return
        self.quests = [quest for quest in self.quests if not quest["completed"]]
        self.save_quests()
        self.rebuild_completed_list()
        self.set_status(f"✧ cleared {count} quest{'s' if count != 1 else ''} from history")
        self.schedule_relayout()

    # ── Quest creator ────────────────────────────────────────────────────────
    def toggle_creator(self, show: bool | None = None) -> None:
        if show is None:
            show = not self.creator.isVisible()
        self.creator.setVisible(show)
        self.new_quest_button.setText(NEW_QUEST_OPEN_TEXT if show else NEW_QUEST_TEXT)
        if show:
            self.activateWindow()
            self.title_input.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.title_input.clear()
            self.custom_input.clear()
            self._clear_creator_errors()
        self.schedule_relayout()

    def _set_input_error(self, widget: QLineEdit, error: bool) -> None:
        widget.setProperty("error", error)
        repolish(widget)

    def _clear_creator_errors(self) -> None:
        self._set_input_error(self.title_input, False)
        self._set_input_error(self.custom_input, False)
        if self.creator_hint.isVisible():
            self.creator_hint.setVisible(False)
            self.schedule_relayout()

    def _show_creator_error(self, widget: QLineEdit, message: str) -> None:
        self._set_input_error(widget, True)
        self.creator_hint.setText(message)
        self.creator_hint.setVisible(True)
        widget.setFocus()
        self.schedule_relayout()

    def submit_new_quest(self) -> None:
        title = " ".join(self.title_input.text().split())
        if not title:
            self._show_creator_error(self.title_input, "✧ your quest needs a name ~")
            return
        rank_button = self.rank_group.checkedButton()
        rank = rank_button.property("rank_value") if rank_button else DEFAULT_RANK

        custom = self.custom_input.text().strip()
        if custom:
            try:
                deadline = datetime.strptime(custom, CUSTOM_DEADLINE_FORMAT)
            except ValueError:
                example = (now_local() + timedelta(days=1)).strftime(CUSTOM_DEADLINE_FORMAT)
                self._show_creator_error(self.custom_input, f"✧ use YYYY-MM-DD HH:MM  (e.g. {example})")
                return
        else:
            preset_button = self.preset_group.checkedButton()
            seconds = preset_button.property("preset_seconds") if preset_button else 86400
            deadline = now_local() + timedelta(seconds=int(seconds))

        quest = {"id": new_quest_id(), "title": title, "rank": rank, "deadline": to_iso(deadline), "completed": False}
        self.quests.append(quest)
        self.save_quests()
        self.rebuild_active_list()
        self.toggle_creator(False)
        self.set_status(f"♡ quest accepted: “{title}” ({RANK_GLYPH[rank]} {rank}-Rank)")

    # ── Status / window lifecycle ────────────────────────────────────────────
    def set_status(self, message: str) -> None:
        self.status_label.setText(f"{message}  ·  {now_local().strftime('%H:%M')}")

    def showEvent(self, event):
        super().showEvent(event)
        self.restore_position()
        self.schedule_relayout()
        if not self._x11_hints_applied:
            self._x11_hints_applied = True
            QTimer.singleShot(250, self._finalize_x11_setup)
            if self.autostart_launch:
                # Re-assert hints & saved position once Xfce panels finish loading
                QTimer.singleShot(2000, self._finalize_x11_setup)

    def _finalize_x11_setup(self) -> None:
        self.restore_position()
        self.apply_x11_hints()
        self._ready = True
        if self.settings["x"] is None or self.settings["y"] is None:
            self._persist_current_pos()

    def apply_x11_hints(self) -> None:
        """Extra Conky-style hints via wmctrl (if installed): all workspaces, no taskbar/pager, below."""
        if QGuiApplication.platformName() != "xcb" or shutil.which("wmctrl") is None:
            return
        window_id = hex(int(self.winId()))
        for props in ("add,sticky", "add,skip_taskbar,skip_pager", "add,below"):
            try:
                subprocess.run(
                    ["wmctrl", "-i", "-r", window_id, "-b", props],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
            except (OSError, subprocess.SubprocessError):
                return


# Backwards-compatible class aliases
SmugQuestBoard = SmugGuildBoard
SakuraGuildBoard = SmugGuildBoard


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    autostart_launch = "--autostart" in args
    if autostart_launch:
        # Give Xfwm4, xfdesktop, and xfce4-panel a moment to settle on login
        time.sleep(2.5)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication([sys.argv[0]] + [a for a in args if a != "--autostart"])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)
    if QGuiApplication.platformName() not in ("xcb", "offscreen", "minimal"):
        print(
            f"✧ {APP_NAME}: desktop pinning works best on X11 (current platform: "
            f"{QGuiApplication.platformName()})",
            file=sys.stderr,
        )
    board = SmugGuildBoard(autostart_launch=autostart_launch)
    board.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
