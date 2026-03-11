"""
Bitcoin Configuration Screen — Full-screen bitcoin.conf editor.

Layout:
  ┌─── Current Config ────┬─── Available Fields ───┐
  │                        │                         │
  │  Your bitcoin.conf     │  All bitcoin.conf opts  │
  │  (live values)         │  grouped by category    │
  │                        ├─── Field Info ──────────┤
  │                        │                         │
  │                        │  Description, default,  │
  │                        │  danger warnings        │
  │                        │                         │
  └────────────────────────┴─────────────────────────┘
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Center
from textual.widgets import Static, Footer, Header, Button
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual import on
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

from bitcoin_terminal.config_data import (
    FIELD_CATEGORIES, ALL_FIELDS, FIELD_TO_CATEGORY, SENSITIVE_KEYS,
    detect_implementation, get_fields_for_impl, IMPLEMENTATIONS,
)

# ── Colors (match tui.py palette) ─────────────────────────────────────
BTC_ORANGE = "#F7931A"
NEON_GREEN = "#39FF14"
SOFT_GREEN = "#00E676"
SOFT_RED = "#FF5252"
SOFT_YELLOW = "#FFD740"
CYAN = "#00BCD4"
PURPLE = "#B388FF"
DIM_BORDER = "#444444"

DANGER_COLORS = {
    "safe": NEON_GREEN,
    "caution": SOFT_YELLOW,
    "danger": SOFT_RED,
}


# ── Save/Restart Dialog ────────────────────────────────────────────────

class SaveRestartDialog(ModalScreen):
    """Modal dialog asking to save and/or restart Bitcoin Core."""

    CSS = """
    SaveRestartDialog {
        align: center middle;
    }
    #save-dialog-box {
        width: 60;
        height: auto;
        max-height: 18;
        background: #111111;
        border: thick $accent;
        padding: 1 2;
    }
    #save-dialog-buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }
    #save-dialog-buttons Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog-box"):
            yield Static(self._build_content())
            with Center(id="save-dialog-buttons"):
                yield Button("Save & Restart Node", id="btn-save-restart",
                             variant="warning")
                yield Button("Save Only", id="btn-save",
                             variant="primary")
                yield Button("Discard", id="btn-discard",
                             variant="default")

    @staticmethod
    def _build_content() -> Text:
        t = Text()
        t.append("\n  ⚠ UNSAVED CHANGES\n\n", style=f"bold {SOFT_YELLOW}")
        t.append("  Your bitcoin.conf has been modified.\n\n",
                 style="white")
        t.append("  • Save & Restart Node", style=f"bold {BTC_ORANGE}")
        t.append(" — write changes and restart bitcoind\n",
                 style="dim")
        t.append("  • Save Only", style=f"bold {CYAN}")
        t.append(" — write changes, restart later\n", style="dim")
        t.append("  • Discard", style="dim")
        t.append(" — throw away all changes\n", style="dim")
        return t

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


# ── Helpers ────────────────────────────────────────────────────────────

def _parse_conf_with_comments(conf_path: Path) -> List[Dict[str, Any]]:
    """Parse bitcoin.conf preserving structure.

    Returns list of dicts: {type: 'setting'|'comment'|'section'|'blank',
                            key, value, raw, line_no}
    """
    entries: List[Dict[str, Any]] = []
    if not conf_path.exists():
        return entries
    try:
        with open(conf_path, 'r') as f:
            for i, raw_line in enumerate(f, 1):
                raw = raw_line.rstrip('\n')
                stripped = raw.strip()
                if not stripped:
                    entries.append({'type': 'blank', 'raw': raw, 'line': i})
                elif stripped.startswith('#'):
                    entries.append({
                        'type': 'comment', 'raw': raw, 'line': i,
                        'text': stripped[1:].strip(),
                    })
                elif stripped.startswith('['):
                    entries.append({
                        'type': 'section', 'raw': raw, 'line': i,
                        'section': stripped.strip('[]').strip(),
                    })
                elif '=' in stripped:
                    key, value = stripped.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    entries.append({
                        'type': 'setting', 'raw': raw, 'line': i,
                        'key': key, 'value': value,
                    })
                else:
                    # Flag-style (no =)
                    entries.append({
                        'type': 'setting', 'raw': raw, 'line': i,
                        'key': stripped, 'value': '1',
                    })
    except (OSError, IOError):
        pass
    return entries


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values."""
    if key.lower() in SENSITIVE_KEYS or 'password' in key.lower():
        if value:
            return '\u2022' * min(len(value), 12)
    return value


def _build_field_index(categories=None) -> List[Tuple[str, str, Tuple]]:
    """Return a flat list of (category, key, field_tuple) for scrolling."""
    cats = categories if categories is not None else FIELD_CATEGORIES
    items = []
    for cat, fields in cats.items():
        for f in fields:
            items.append((cat, f[0], f))
    return items


# ── Widgets ────────────────────────────────────────────────────────────

class CurrentConfigPanel(Static):
    """Left panel: shows the user's current bitcoin.conf settings."""

    def __init__(self, conf_path: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conf_path = conf_path
        self.entries = _parse_conf_with_comments(conf_path)

    def render(self) -> Panel:
        if not self.entries:
            content = Text()
            content.append("  No bitcoin.conf found\n", style="dim italic")
            content.append(f"\n  Expected at:\n  {self.conf_path}",
                           style="dim")
            return Panel(content,
                         title=f"[bold {BTC_ORANGE}]⚙ YOUR CONFIG[/]",
                         border_style=BTC_ORANGE, box=box.ROUNDED)

        content = Text()

        # Count active settings
        settings = [e for e in self.entries if e['type'] == 'setting']
        content.append(f" {len(settings)} active settings\n",
                       style=f"bold {NEON_GREEN}")
        content.append(f" {self.conf_path}\n\n", style="dim")

        for entry in self.entries:
            if entry['type'] == 'blank':
                content.append('\n')
            elif entry['type'] == 'comment':
                content.append(f" # {entry['text']}\n", style="dim italic")
            elif entry['type'] == 'section':
                content.append(f" [{entry['section']}]\n",
                               style=f"bold {CYAN}")
            elif entry['type'] == 'setting':
                key = entry['key']
                value = entry['value']

                # Color-code the key based on danger level
                field_info = ALL_FIELDS.get(key)
                if field_info:
                    danger = field_info[4]
                    key_color = DANGER_COLORS.get(danger, "white")
                else:
                    key_color = "white"

                # Check if it's in the known database
                known_marker = "● " if field_info else "○ "
                marker_color = NEON_GREEN if field_info else "dim"
                content.append(f" {known_marker}", style=marker_color)

                content.append(f"{key}", style=f"bold {key_color}")
                content.append("=", style="dim")

                # Mask sensitive values
                display_val = _mask_value(key, value)

                # Color the value
                if display_val.startswith('\u2022'):
                    content.append(display_val, style="dim")
                elif value in ('1', 'true', 'yes'):
                    content.append(display_val, style=NEON_GREEN)
                elif value in ('0', 'false', 'no'):
                    content.append(display_val, style="dim")
                else:
                    content.append(display_val, style="white")

                # Show danger warning inline
                if field_info and field_info[4] == 'danger':
                    content.append("  ⚠", style=f"bold {SOFT_RED}")

                content.append('\n')

        return Panel(content,
                     title=f"[bold {BTC_ORANGE}]⚙ YOUR CONFIG[/]",
                     subtitle=f"[dim]{len(settings)} settings[/]",
                     border_style=BTC_ORANGE, box=box.ROUNDED)


class AvailableFieldsPanel(Static):
    """Right-top panel: all available bitcoin.conf fields by category."""

    cursor = reactive(0)

    def __init__(self, active_keys: frozenset, categories=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_keys = active_keys
        self.field_index = _build_field_index(categories)

    def get_selected_field(self) -> Optional[Tuple]:
        """Return the currently highlighted field tuple."""
        if 0 <= self.cursor < len(self.field_index):
            return self.field_index[self.cursor]
        return None

    def move_cursor(self, delta: int):
        old = self.cursor
        self.cursor = max(0, min(len(self.field_index) - 1,
                                 self.cursor + delta))
        if self.cursor != old:
            self.refresh()

    def render(self) -> Panel:
        content = Text()
        last_cat = None

        # Calculate visible window around cursor
        total = len(self.field_index)
        # We want to show as much as possible — estimate ~30 visible lines
        # and keep cursor roughly centered
        visible_lines = 40
        lines_before_cursor = 0
        line_data = []  # (line_text, style, is_cursor_line)

        for idx, (cat, key, field) in enumerate(self.field_index):
            if cat != last_cat:
                line_data.append((f"\n {cat}\n", f"bold {CYAN}", False))
                last_cat = cat

            is_active = key in self.active_keys
            is_cursor = idx == self.cursor
            danger = field[4]
            impl_tag = field[5] if len(field) > 5 else "all"

            # Build the line
            marker = "✓" if is_active else " "
            marker_color = NEON_GREEN if is_active else "dim"

            if is_cursor:
                lines_before_cursor = len(line_data)

            line_data.append((marker, marker_color, is_cursor, key, danger,
                              is_active, impl_tag))

        # Window the output
        start = max(0, lines_before_cursor - visible_lines // 3)
        end = start + visible_lines

        for item in line_data[start:end]:
            if len(item) == 3:
                # Category header
                text, style, _ = item
                content.append(text, style=style)
            else:
                marker, marker_color, is_cursor, key, danger, is_active, impl_tag = item
                danger_color = DANGER_COLORS.get(danger, "white")

                if is_cursor:
                    content.append(" ▸ ", style=f"bold {BTC_ORANGE}")
                    content.append(f"{marker} ", style=marker_color)
                    content.append(f"{key}", style=f"bold reverse {danger_color}")
                else:
                    content.append("   ", style="dim")
                    content.append(f"{marker} ", style=marker_color)
                    content.append(f"{key}", style=danger_color if is_active
                                   else "dim" if danger == "safe"
                                   else danger_color)

                if impl_tag != "all":
                    content.append(f" [{impl_tag}]", style="dim italic")
                if danger == "danger":
                    content.append(" ⚠", style=f"bold {SOFT_RED}")
                elif danger == "caution":
                    content.append(" ●", style=SOFT_YELLOW)

                content.append('\n')

        pos = f"{self.cursor + 1}/{total}"
        return Panel(content,
                     title=f"[bold {CYAN}]📋 AVAILABLE FIELDS[/]",
                     subtitle=f"[dim]{pos}  ↑↓ scroll[/]",
                     border_style=CYAN, box=box.ROUNDED)


class FieldInfoPanel(Static):
    """Right-bottom panel: detailed explanation of the highlighted field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_data: Optional[Tuple] = None
        self.is_active: bool = False
        self.current_value: str = ""

    def update_field(self, field_data: Optional[Tuple], is_active: bool = False,
                     current_value: str = ""):
        changed = (field_data != self.field_data or is_active != self.is_active
                   or current_value != self.current_value)
        self.field_data = field_data
        self.is_active = is_active
        self.current_value = current_value
        if changed:
            self.refresh()

    def render(self) -> Panel:
        if not self.field_data:
            content = Text()
            content.append("  Select a field above to see details\n",
                           style="dim italic")
            content.append("\n  ↑/↓  Navigate fields\n", style="dim")
            content.append("  q    Return to dashboard\n", style="dim")
            return Panel(content,
                         title=f"[bold {PURPLE}]📖 FIELD INFO[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        key, default, ftype, description, danger = self.field_data[:5]
        impl_tag = self.field_data[5] if len(self.field_data) > 5 else "all"
        category = FIELD_TO_CATEGORY.get(key, "")

        content = Text()

        # Field name — big and bold
        danger_color = DANGER_COLORS.get(danger, "white")
        content.append(f"  {key}\n", style=f"bold {danger_color}")

        # Category
        content.append(f"  {category}", style=f"dim {CYAN}")
        if impl_tag != "all":
            impl_info = IMPLEMENTATIONS.get(impl_tag, {})
            impl_name = impl_info.get('name', impl_tag)
            impl_icon = impl_info.get('icon', '')
            content.append(f"  {impl_icon} {impl_name} only",
                           style="dim italic")
        content.append('\n\n')

        # Status badge
        if self.is_active:
            content.append("  STATUS  ", style=f"bold on {NEON_GREEN} #000000")
            content.append(f"  In your config", style=NEON_GREEN)
            if self.current_value:
                masked = _mask_value(key, self.current_value)
                content.append(f" = {masked}", style="bold white")
            content.append('\n')
        else:
            content.append("  STATUS  ", style="bold on #333333 white")
            content.append("  Not in your config\n", style="dim")

        # Default value
        content.append(f"  Default: ", style="dim")
        content.append(f"{default or '(none)'}\n", style="white")

        # Type
        type_labels = {
            'bool': '0 or 1',
            'int': 'number',
            'string': 'text',
            'path': 'file path',
            'multi': 'text (can repeat)',
        }
        content.append(f"  Type:    ", style="dim")
        content.append(f"{type_labels.get(ftype, ftype)}\n\n", style="white")

        # Danger level badge
        if danger == "danger":
            content.append("  ⚠ DANGEROUS ", style=f"bold on {SOFT_RED} white")
            content.append(
                "  Misconfiguring this can compromise security\n"
                "  or expose your node. Proceed with caution.\n\n",
                style=f"bold {SOFT_RED}")
        elif danger == "caution":
            content.append("  ● CAUTION ", style=f"bold on {SOFT_YELLOW} #000000")
            content.append(
                "  Changing this affects node behavior.\n"
                "  Understand the implications first.\n\n",
                style=SOFT_YELLOW)
        else:
            content.append("  ✓ SAFE ", style=f"bold on {NEON_GREEN} #000000")
            content.append(
                "  This setting is safe to change.\n\n",
                style="dim")

        # Description — word-wrapped
        content.append("  ", style="dim")
        # Wrap description with left padding
        words = description.split()
        line_len = 2
        for word in words:
            if line_len + len(word) + 1 > 56:
                content.append('\n  ')
                line_len = 2
            if word.startswith('⚠'):
                content.append(f"{word} ", style=f"bold {SOFT_RED}")
            else:
                content.append(f"{word} ", style="white")
            line_len += len(word) + 1
        content.append('\n')

        return Panel(content,
                     title=f"[bold {PURPLE}]📖 FIELD INFO[/]",
                     border_style=PURPLE, box=box.ROUNDED)


# ── Main Screen ────────────────────────────────────────────────────────

class ConfigScreen(Screen):
    """Full-screen bitcoin.conf editor and reference."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("j", "cursor_down", "Down"),
        ("enter", "toggle_field", "Toggle"),
        ("R", "restart_node", "Restart Node"),
        ("pageup", "page_up", "Page Up"),
        ("pagedown", "page_down", "Page Down"),
    ]

    CSS = """
    ConfigScreen {
        background: #0a0a0a;
    }
    #config-screen-header {
        height: 1;
        content-align: center middle;
        background: #111111;
        margin: 0 1;
    }
    #config-stats-bar {
        height: 1;
        content-align: center middle;
        background: #0d0d0d;
        margin: 0 1;
    }
    #config-layout {
        height: 1fr;
    }
    #config-left {
        width: 1fr;
        height: 100%;
        overflow-y: auto;
    }
    #config-right {
        width: 1fr;
        height: 100%;
    }
    #config-right-top {
        height: 2fr;
        overflow-y: auto;
    }
    #config-right-bottom {
        height: 1fr;
        overflow-y: auto;
    }
    #config-footer {
        height: 1;
        background: #111111;
        content-align: center middle;
        margin: 0 1;
    }
    """

    def __init__(self, conf_path: Path, subversion: str = "",
                 system_metrics: Optional[Dict] = None,
                 block_time_stats: Optional[Dict] = None,
                 rpc=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conf_path = conf_path
        self.rpc = rpc
        self.impl_info = detect_implementation(subversion)
        self.impl_categories = get_fields_for_impl(self.impl_info['id'])
        self.system_metrics = system_metrics or {}
        self.block_time_stats = block_time_stats or {}
        self._dirty = False
        # Parse config to know which keys are active
        self._reload_conf()

    def compose(self) -> ComposeResult:
        header_text = Text()
        header_text.append("₿ ", style=f"bold {BTC_ORANGE}")
        header_text.append("BITCOIN CONFIGURATION", style=f"bold {BTC_ORANGE}")
        header_text.append("  •  ", style="dim")
        # Implementation badge
        imp = self.impl_info
        header_text.append(f"{imp['icon']} {imp['name']}",
                           style=f"bold {NEON_GREEN}")
        if imp['version']:
            header_text.append(f" v{imp['version']}", style=f"{NEON_GREEN}")

        # System health snapshot
        sm = self.system_metrics
        if sm:
            header_text.append("  •  ", style="dim")
            cpu_temp = sm.get('cpu_temp')
            if cpu_temp is not None:
                tc = NEON_GREEN if cpu_temp < 65 else (
                    SOFT_YELLOW if cpu_temp < 80 else SOFT_RED)
                header_text.append(f"{cpu_temp:.0f}°C", style=f"bold {tc}")
                header_text.append("  ", style="dim")
            cpu_pct = sm.get('cpu_percent')
            if cpu_pct is not None:
                cc = NEON_GREEN if cpu_pct < 60 else (
                    SOFT_YELLOW if cpu_pct < 85 else SOFT_RED)
                header_text.append(f"CPU {cpu_pct:.0f}%", style=cc)
                header_text.append("  ", style="dim")
            mem_pct = sm.get('mem_percent')
            if mem_pct is not None:
                mc = NEON_GREEN if mem_pct < 70 else (
                    SOFT_YELLOW if mem_pct < 90 else SOFT_RED)
                header_text.append(f"MEM {mem_pct:.0f}%", style=mc)
                header_text.append("  ", style="dim")
            disk_pct = sm.get('disk_percent')
            if disk_pct is not None:
                dc = NEON_GREEN if disk_pct < 75 else (
                    SOFT_YELLOW if disk_pct < 90 else SOFT_RED)
                header_text.append(f"DISK {disk_pct:.0f}%", style=dc)

        header_text.append("  •  ", style="dim")
        header_text.append(str(self.conf_path), style="dim")
        yield Static(header_text, id="config-screen-header")

        # Block timing stats bar
        stats_text = self._build_block_timing_bar()
        yield Static(stats_text, id="config-stats-bar")

        with Horizontal(id="config-layout"):
            yield CurrentConfigPanel(self.conf_path, id="config-left")
            with Vertical(id="config-right"):
                yield AvailableFieldsPanel(self.active_keys,
                                           self.impl_categories,
                                           id="config-right-top")
                yield FieldInfoPanel(id="config-right-bottom")

        footer_text = Text()
        footer_text.append(" ↑↓ ", style=f"bold {BTC_ORANGE}")
        footer_text.append("Navigate  ", style="dim")
        footer_text.append(" Enter ", style=f"bold {BTC_ORANGE}")
        footer_text.append("Toggle  ", style="dim")
        footer_text.append(" R ", style=f"bold {SOFT_YELLOW}")
        footer_text.append("Restart Node  ", style="dim")
        footer_text.append(" q/Esc ", style=f"bold {BTC_ORANGE}")
        footer_text.append("Back  ", style="dim")
        footer_text.append(" ✓ ", style=f"bold {NEON_GREEN}")
        footer_text.append("= active  ", style="dim")
        footer_text.append(" ⚠ ", style=f"bold {SOFT_RED}")
        footer_text.append("= dangerous", style="dim")
        yield Static(footer_text, id="config-footer")

    def on_mount(self) -> None:
        self._update_info_panel()

    @staticmethod
    def _speed_label(avg_secs):
        """Classify block speed: fast / normal / slow."""
        if avg_secs is None:
            return None, "dim"
        if avg_secs < 540:        # < 9 min
            return "fast", NEON_GREEN
        elif avg_secs <= 660:     # 9–11 min
            return "normal", CYAN
        else:                     # > 11 min
            return "slow", SOFT_YELLOW

    def _build_block_timing_bar(self) -> Text:
        """Build the block timing stats bar text."""
        t = Text()
        bts = self.block_time_stats
        if not bts:
            t.append("  ⏱ Block timing data unavailable", style="dim")
            return t

        t.append("  ⏱ ", style=f"bold {BTC_ORANGE}")

        epoch_avg = bts.get('epoch_avg')
        if epoch_avg is not None:
            mins = int(epoch_avg // 60)
            secs = int(epoch_avg % 60)
            label, color = self._speed_label(epoch_avg)
            t.append("Epoch avg: ", style="dim")
            t.append(f"{mins}m {secs}s", style=f"bold {color}")
            if label:
                t.append(f" ({label})", style=color)
            blocks_in = bts.get('blocks_in_epoch', 0)
            t.append(f"  [{blocks_in}/2016]", style="dim")
        else:
            t.append("Epoch avg: ", style="dim")
            t.append("—", style="dim")

        t.append("    ", style="dim")

        avg_24h = bts.get('avg_24h')
        if avg_24h is not None:
            mins = int(avg_24h // 60)
            secs = int(avg_24h % 60)
            label, color = self._speed_label(avg_24h)
            t.append("24h avg: ", style="dim")
            t.append(f"{mins}m {secs}s", style=f"bold {color}")
            if label:
                t.append(f" ({label})", style=color)
        else:
            t.append("24h avg: ", style="dim")
            t.append("—", style="dim")

        # Target reference
        t.append("    target: 10m 0s", style="dim italic")

        # Hashprice
        hp = bts.get('hashprice')
        if hp is not None:
            t.append("    ", style="dim")
            t.append("Hashprice: ", style="dim")
            t.append(f"${hp:,.2f}", style=f"bold {NEON_GREEN}")
            t.append("/PH/day", style="dim")

        # Avg fee as % of block reward
        fee_pct = bts.get('avg_fee_pct')
        if fee_pct is not None:
            t.append("    ", style="dim")
            t.append("Fees: ", style="dim")
            fc = NEON_GREEN if fee_pct < 10 else (
                SOFT_YELLOW if fee_pct < 50 else BTC_ORANGE)
            t.append(f"{fee_pct:.1f}%", style=f"bold {fc}")
            t.append(" of reward", style="dim")

        # Hashrate ATH & drawdown
        hr_ath = bts.get('hashrate_ath')
        hr_dd = bts.get('hashrate_dd')
        if hr_ath is not None:
            from bitcoin_terminal.data import format_hashrate
            t.append("    ", style="dim")
            t.append("HR ATH: ", style="dim")
            t.append(format_hashrate(hr_ath), style=f"bold {NEON_GREEN}")
            if hr_dd is not None:
                if hr_dd <= 0:
                    t.append(" (ATH ✔)", style=f"bold {NEON_GREEN}")
                else:
                    dc = NEON_GREEN if hr_dd < 5 else (
                        SOFT_YELLOW if hr_dd < 15 else SOFT_RED)
                    t.append(f" (-{hr_dd:.1f}%)", style=f"bold {dc}")

        return t

    def _update_info_panel(self) -> None:
        """Sync the info panel with the currently selected field."""
        fields_panel = self.query_one("#config-right-top",
                                      AvailableFieldsPanel)
        info_panel = self.query_one("#config-right-bottom", FieldInfoPanel)
        selected = fields_panel.get_selected_field()
        if selected:
            cat, key, field = selected
            is_active = key in self.active_keys
            current_value = self.active_settings.get(key, "")
            info_panel.update_field(field, is_active, current_value)
        else:
            info_panel.update_field(None)

    def action_cursor_up(self) -> None:
        panel = self.query_one("#config-right-top", AvailableFieldsPanel)
        panel.move_cursor(-1)
        self._update_info_panel()

    def action_cursor_down(self) -> None:
        panel = self.query_one("#config-right-top", AvailableFieldsPanel)
        panel.move_cursor(1)
        self._update_info_panel()

    def action_page_up(self) -> None:
        panel = self.query_one("#config-right-top", AvailableFieldsPanel)
        panel.move_cursor(-10)
        self._update_info_panel()

    def action_page_down(self) -> None:
        panel = self.query_one("#config-right-top", AvailableFieldsPanel)
        panel.move_cursor(10)
        self._update_info_panel()

    def _reload_conf(self) -> None:
        """Re-parse bitcoin.conf and update active keys."""
        entries = _parse_conf_with_comments(self.conf_path)
        self.active_settings: Dict[str, str] = {}
        for e in entries:
            if e['type'] == 'setting':
                self.active_settings[e['key']] = e['value']
        self.active_keys = frozenset(self.active_settings.keys())

    def _refresh_panels(self) -> None:
        """Refresh all panels after a config change."""
        # Refresh left panel (current config)
        left = self.query_one("#config-left", CurrentConfigPanel)
        left.entries = _parse_conf_with_comments(self.conf_path)
        left.refresh()

        # Refresh available fields panel with updated active keys
        fields_panel = self.query_one("#config-right-top",
                                       AvailableFieldsPanel)
        fields_panel.active_keys = self.active_keys
        fields_panel.refresh()

        # Update info panel
        self._update_info_panel()

    def action_toggle_field(self) -> None:
        """Add or remove the selected field from bitcoin.conf."""
        fields_panel = self.query_one("#config-right-top",
                                       AvailableFieldsPanel)
        selected = fields_panel.get_selected_field()
        if not selected:
            return

        cat, key, field = selected
        default_val = field[1]  # default value from field tuple
        ftype = field[2]

        if key in self.active_keys:
            # ── Remove from config ────────────────────────────────
            self._remove_field(key)
            self.notify(f"Removed: {key}", timeout=2)
        else:
            # ── Add to config with default value ──────────────────
            if ftype == 'bool':
                value = default_val if default_val else '1'
            else:
                value = default_val if default_val else ''
            self._add_field(key, value)
            self.notify(f"Added: {key}={value}", timeout=2)

        self._dirty = True
        self._reload_conf()
        self._refresh_panels()

    def _add_field(self, key: str, value: str) -> None:
        """Append a setting to bitcoin.conf."""
        try:
            with open(self.conf_path, 'a') as f:
                f.write(f"\n{key}={value}\n")
        except OSError as e:
            self.notify(f"Error writing config: {e}",
                        severity="error", timeout=3)

    def _remove_field(self, key: str) -> None:
        """Remove (comment out) a setting from bitcoin.conf."""
        try:
            lines = self.conf_path.read_text().splitlines(keepends=True)
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#') or not stripped:
                    new_lines.append(line)
                    continue
                line_key = stripped.split('=', 1)[0].strip()
                if line_key == key:
                    # Comment it out, preserving the original line
                    new_lines.append(f"# {stripped}\n")
                else:
                    new_lines.append(line)
            self.conf_path.write_text(''.join(new_lines))
        except OSError as e:
            self.notify(f"Error writing config: {e}",
                        severity="error", timeout=3)

    def action_restart_node(self) -> None:
        """Restart Bitcoin Core via keybinding."""
        self._restart_bitcoin()

    def _restart_bitcoin(self) -> None:
        """Stop the node via RPC, then attempt a restart."""
        # Stop via RPC
        if self.rpc:
            try:
                self.rpc.call('stop')
                self.notify("Bitcoin Core stopping...", timeout=3)
            except Exception:
                self.notify("RPC stop failed — stop node manually",
                            severity="warning", timeout=4)
                return
        else:
            self.notify("No RPC connection — stop node manually",
                        severity="warning", timeout=4)
            return

        # Try to restart via bitcoind in background
        bitcoind = shutil.which('bitcoind')
        if bitcoind:
            try:
                subprocess.Popen(
                    [bitcoind, f'-datadir={self.conf_path.parent}',
                     '-daemon'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.notify("bitcoind restarting...", timeout=3)
            except Exception:
                self.notify(
                    "Stopped node. Start it manually with: bitcoind -daemon",
                    severity="warning", timeout=5)
        else:
            self.notify(
                "Stopped node. bitcoind not in PATH — start manually",
                severity="warning", timeout=5)

    def _on_dialog_result(self, result: str) -> None:
        """Handle the save/restart dialog result."""
        if result == "btn-save-restart":
            self._restart_bitcoin()
            self.app.pop_screen()  # pop config screen
        elif result == "btn-save":
            self.notify("Config saved. Restart node to apply changes.",
                        timeout=3)
            self.app.pop_screen()
        elif result == "btn-discard":
            # Discard is trickier — we already wrote changes per-toggle.
            # We can't easily undo, but user chose discard, so just leave.
            self.notify("Changes already written to file.",
                        severity="warning", timeout=3)
            self._dirty = False
            self.app.pop_screen()
        else:
            # Dialog dismissed some other way
            pass

    def action_go_back(self) -> None:
        if self._dirty:
            self.app.push_screen(SaveRestartDialog(),
                                 callback=self._on_dialog_result)
        else:
            self.app.pop_screen()
