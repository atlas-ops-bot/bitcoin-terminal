"""
Display Settings Screen — toggle cards, status bar items, and figlet font.

Layout:
  ┌── Card Visibility ──┬── Status Bar Items ──┐
  │  ☑ Price Card        │  ☑ Price             │
  │  ☑ Block Height      │  ☑ Hashprice         │
  │  ☑ Node              │  ☑ Epoch Avg         │
  │  …                   │  ☑ Fee %             │
  │                      │  …                   │
  ├── Font Settings ─────┴────────────────────┤
  │  Font: [◀ small ▶]                          │
  │  Preview: (live figlet render)              │
  └─────────────────────────────────────────────┘
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import pyfiglet
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Footer
from textual.screen import Screen
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

# ── Colors (match tui.py palette) ─────────────────────────────────────
BTC_ORANGE = "#F7931A"
NEON_GREEN = "#39FF14"
SOFT_GREEN = "#00E676"
SOFT_RED = "#FF5252"
SOFT_YELLOW = "#FFD740"
CYAN = "#00BCD4"
PURPLE = "#B388FF"
DIM_BORDER = "#444444"

# ── Curated figlet fonts that render numbers/$ well ───────────────────
FIGLET_FONTS = [
    'small',       # default — compact 4-line
    'standard',    # classic figlet
    'big',         # tall, bold
    'slant',       # italic lean
    'smslant',     # small italic
    'banner',      # block style
    'block',       # heavy 3D
    'bubble',      # rounded
    'digital',     # LCD style
    'lean',        # thin italic
    'mini',        # tiny 2-line
    'script',      # cursive
    'shadow',      # with drop shadow
    'term',        # terminal — just the chars
    'chunky',      # chunky block
    'cybermedium', # clean digital
    'ansi_shadow', # ANSI art shadow
    'calvin_s',    # tiny 3-line
    'bigfig',      # compact big
    'bulbhead',    # rounded block
    'ogre',        # organic
    'doom',        # doom-style
    'larry3d',     # 3D perspective
    'colossal',    # giant
]

# Validate fonts exist at import time
FIGLET_FONTS = [f for f in FIGLET_FONTS if f in pyfiglet.FigletFont.getFonts()]

# ── Card & Header Item Definitions ────────────────────────────────────
CARD_DEFS = [
    ('block_height', '⛏ Block Height',  'Hero row — large ASCII block number'),
    ('price',        '₿ BTC Price',      'Hero row — large ASCII BTC price'),
    ('node',         '⧫ Node',           'Sync status, version, uptime'),
    ('network',      '⇄ P2P Peers',      'Peer connections, bandwidth'),
    ('market',       '≡ Market',         'Market cap, ATH, supply'),
    ('mempool',      '⏱ Mempool',        'Pending txns, memory, fees'),
    ('blockchain',   '⛓ Blockchain',     'Difficulty, hashrate, adjustment'),
    ('halving',      '½ Halving',        'Countdown to next halving'),
    ('rpc',          '⚒ RPC',            'RPC request monitoring'),
    ('system',       '⚙ System',         'CPU, memory, disk, temp'),
    ('satoshi',      '✦ Satoshi',        'Rotating Nakamoto quotes'),
]

HEADER_DEFS = [
    ('status',    '● Status',     'Synced / Syncing / Offline'),
    ('chain',     'MAIN',         'Chain name (main/test/signet)'),
    ('blocks',    '⦫ Blocks',     'Current block height'),
    ('peers',     '⇄ Peers',      'Peer connection count'),
    ('price',     '$ Price',      'Current BTC price'),
    ('hashprice', '$/PH',         'Mining hashprice'),
    ('epoch_avg', '⏱ Epoch',      'Epoch average block time'),
    ('fee_pct',   'Fee %',        'Fees as % of block reward'),
    ('time',      '🕐 Time',      'Current time'),
]

# ── Settings file path ────────────────────────────────────────────────
SETTINGS_FILE = Path(__file__).parent.parent / '.display_settings.json'


def load_display_settings() -> Dict[str, Any]:
    """Load settings from JSON, returning defaults if missing."""
    defaults = {
        'visible_cards': {d[0]: True for d in CARD_DEFS},
        'visible_header': {d[0]: True for d in HEADER_DEFS},
        'figlet_font': 'small',
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
            # Merge with defaults (add any new keys)
            for section in ('visible_cards', 'visible_header'):
                if section in saved:
                    for key in defaults[section]:
                        if key not in saved[section]:
                            saved[section][key] = defaults[section][key]
                else:
                    saved[section] = defaults[section]
            if 'figlet_font' not in saved:
                saved['figlet_font'] = defaults['figlet_font']
            return saved
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return defaults


def save_display_settings(settings: Dict[str, Any]) -> None:
    """Persist settings to JSON."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


# ── Widgets ───────────────────────────────────────────────────────────

class ToggleList(Static):
    """A panel of toggleable items with labels."""

    selected_idx = reactive(0)

    def __init__(self, title: str, items: list, states: Dict[str, bool],
                 color: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.items = items          # [(key, label, description)]
        self.states = dict(states)  # {key: bool}
        self.color = color

    def toggle_current(self):
        key = self.items[self.selected_idx][0]
        self.states[key] = not self.states[key]
        self.refresh()

    def move_up(self):
        if self.selected_idx > 0:
            self.selected_idx -= 1
            self.refresh()

    def move_down(self):
        if self.selected_idx < len(self.items) - 1:
            self.selected_idx += 1
            self.refresh()

    def render(self) -> Panel:
        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("toggle", width=3)
        t.add_column("label", ratio=2)
        t.add_column("desc", ratio=3)

        for i, (key, label, desc) in enumerate(self.items):
            on = self.states.get(key, True)
            check = Text("☑ " if on else "☐ ",
                         style=f"bold {NEON_GREEN}" if on else f"dim {SOFT_RED}")
            name = Text(label, style="bold white" if on else "dim")
            d = Text(desc, style="dim" if on else "dim strike")

            if i == self.selected_idx:
                # Highlight row
                check.stylize(f"reverse bold {self.color}")
                name.stylize(f"reverse bold {self.color}")
                d.stylize(f"reverse {self.color}")

            t.add_row(check, name, d)

        return Panel(t, title=f"[bold {self.color}]{self.title}[/]",
                     border_style=self.color, box=box.ROUNDED)


class FontPreview(Static):
    """Live figlet font preview."""

    font_name = reactive("small")
    _font_idx = 0

    def __init__(self, current_font: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_name = current_font
        if current_font in FIGLET_FONTS:
            self._font_idx = FIGLET_FONTS.index(current_font)

    def next_font(self):
        self._font_idx = (self._font_idx + 1) % len(FIGLET_FONTS)
        self.font_name = FIGLET_FONTS[self._font_idx]

    def prev_font(self):
        self._font_idx = (self._font_idx - 1) % len(FIGLET_FONTS)
        self.font_name = FIGLET_FONTS[self._font_idx]

    def render(self) -> Panel:
        t = Text()

        # Font selector line
        t.append("  Font: ", style="dim")
        t.append("◀ ", style=f"bold {CYAN}")
        t.append(self.font_name, style=f"bold {NEON_GREEN}")
        t.append(" ▶", style=f"bold {CYAN}")
        t.append(f"  ({self._font_idx + 1}/{len(FIGLET_FONTS)})", style="dim")
        t.append("      ← / → to change", style="dim italic")
        t.append("\n\n")

        # Figlet preview
        try:
            fig = pyfiglet.Figlet(font=self.font_name, width=120)
            preview_price = fig.renderText("$ 97,543")
            price_lines = [l for l in preview_price.split('\n') if l.strip()]
            for line in price_lines:
                t.append(line + '\n', style=f"bold {NEON_GREEN}")

            t.append("\n")

            preview_block = fig.renderText("893,421")
            block_lines = [l for l in preview_block.split('\n') if l.strip()]
            for line in block_lines:
                t.append(line + '\n', style=f"bold {BTC_ORANGE}")
        except Exception:
            t.append("  (font preview unavailable)", style="dim italic")

        return Panel(t,
                     title=f"[bold {PURPLE}]⬡ FONT PREVIEW[/]",
                     border_style=PURPLE, box=box.ROUNDED)


# ── Main Screen ───────────────────────────────────────────────────────

class DisplaySettingsScreen(Screen):
    """Full-screen display settings editor."""

    CSS = """
    DisplaySettingsScreen {
        background: #0a0a0a;
    }
    #ds-header {
        height: 1;
        content-align: center middle;
        background: #111111;
        margin: 0 1;
    }
    #ds-top-row {
        height: 1fr;
    }
    #ds-cards-panel {
        width: 1fr;
        height: 100%;
        overflow-y: auto;
    }
    #ds-header-panel {
        width: 1fr;
        height: 100%;
        overflow-y: auto;
    }
    #ds-font-panel {
        height: auto;
        max-height: 20;
        overflow-y: auto;
    }
    #ds-footer {
        height: 1;
        background: #111111;
        content-align: center middle;
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("q",     "go_back",    "Back"),
        ("escape", "go_back",   "Back"),
        ("up",    "move_up",    "Up"),
        ("k",     "move_up",    "Up"),
        ("down",  "move_down",  "Down"),
        ("j",     "move_down",  "Down"),
        ("enter", "toggle",     "Toggle"),
        ("space", "toggle",     "Toggle"),
        ("tab",   "next_panel", "Next Panel"),
        ("left",  "font_prev",  "Prev Font"),
        ("right", "font_next",  "Next Font"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = load_display_settings()
        self._active_panel = 0  # 0=cards, 1=header, 2=font
        self._panels: List = []

    def compose(self) -> ComposeResult:
        header = Text()
        header.append("₿ ", style=f"bold {BTC_ORANGE}")
        header.append("DISPLAY SETTINGS", style=f"bold {BTC_ORANGE}")
        header.append("   Toggle cards, status bar items, and ASCII font",
                       style="dim")
        yield Static(header, id="ds-header")

        self.cards_list = ToggleList(
            "⬡ DASHBOARD CARDS",
            CARD_DEFS,
            self.settings['visible_cards'],
            BTC_ORANGE,
            id="ds-cards-panel",
        )
        self.header_list = ToggleList(
            "≡ STATUS BAR ITEMS",
            HEADER_DEFS,
            self.settings['visible_header'],
            CYAN,
            id="ds-header-panel",
        )
        self.font_preview = FontPreview(
            self.settings.get('figlet_font', 'small'),
            id="ds-font-panel",
        )

        with Horizontal(id="ds-top-row"):
            yield self.cards_list
            yield self.header_list

        yield self.font_preview

        self._panels = [self.cards_list, self.header_list, self.font_preview]
        self._highlight_active()

        footer = Text()
        footer.append(" ↑↓/jk ", style=f"bold {BTC_ORANGE}")
        footer.append("Navigate  ", style="dim")
        footer.append(" Enter/Space ", style=f"bold {BTC_ORANGE}")
        footer.append("Toggle  ", style="dim")
        footer.append(" Tab ", style=f"bold {CYAN}")
        footer.append("Switch Panel  ", style="dim")
        footer.append(" ←→ ", style=f"bold {PURPLE}")
        footer.append("Change Font  ", style="dim")
        footer.append(" q/Esc ", style=f"bold {BTC_ORANGE}")
        footer.append("Save & Back", style="dim")
        yield Static(footer, id="ds-footer")

    def _highlight_active(self):
        for i, panel in enumerate(self._panels):
            if i == self._active_panel:
                panel.styles.border = ("round", NEON_GREEN)
            else:
                panel.styles.border = None

    def _active_widget(self):
        if self._panels:
            return self._panels[self._active_panel]
        return None

    def action_next_panel(self):
        self._active_panel = (self._active_panel + 1) % len(self._panels)
        self._highlight_active()

    def action_move_up(self):
        w = self._active_widget()
        if isinstance(w, ToggleList):
            w.move_up()

    def action_move_down(self):
        w = self._active_widget()
        if isinstance(w, ToggleList):
            w.move_down()

    def action_toggle(self):
        w = self._active_widget()
        if isinstance(w, ToggleList):
            w.toggle_current()

    def action_font_prev(self):
        self.font_preview.prev_font()

    def action_font_next(self):
        self.font_preview.next_font()

    def action_go_back(self):
        # Collect final state and save
        self.settings['visible_cards'] = self.cards_list.states
        self.settings['visible_header'] = self.header_list.states
        self.settings['figlet_font'] = self.font_preview.font_name
        save_display_settings(self.settings)
        self.dismiss(True)

    def on_mount(self):
        self._highlight_active()
