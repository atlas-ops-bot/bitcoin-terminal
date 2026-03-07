"""
Real-time Bitcoin Core debug.log viewer.

Tails debug.log asynchronously, formats each line into a single
readable, color-coded row — no raw hashes, no noise.

Navigation: press  L  (or Esc) to return to the dashboard.
"""

import re
import threading
import time
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, RichLog, Static
from textual.containers import Container
from rich.text import Text

# ── Color aliases (match tui.py palette) ─────────────────────────────────────
BTC_ORANGE  = "#F7931A"
NEON_GREEN  = "#39FF14"
SOFT_GREEN  = "#00E676"
SOFT_RED    = "#FF5252"
SOFT_YELLOW = "#FFD740"
CYAN        = "#00BCD4"
PURPLE      = "#B388FF"
DIM_BORDER  = "#444444"

# ── Regexes ───────────────────────────────────────────────────────────────────

# Bitcoin Core timestamp: 2026-03-07T11:12:44Z  (fractional seconds are optional)
_TS_RE   = re.compile(r'^(\d{4}-\d{2}-\d{2}T)(\d{2}:\d{2}:\d{2})(?:\.\d+)?Z\s*')

# 64-char SHA-256 hex hash
_HASH64  = re.compile(r'\b([0-9a-fA-F]{64})\b')
# 32–63 char hex (shorter txids / block hashes in truncated form)
_HASH32  = re.compile(r'\b([0-9a-fA-F]{40,63})\b')

# IPv4 address
_IPv4    = re.compile(r'\b(\d{1,3}(?:\.\d{1,3}){3}(:\d+)?)\b')
# Tor .onion
_ONION   = re.compile(r'\b(\w{16,56}\.onion(?::\d+)?)\b')
# peer=N
_PEER    = re.compile(r'\bpeer=(\d+)\b')
# height=N or height: N
_HEIGHT  = re.compile(r'\bheight[=:](\d+)\b', re.IGNORECASE)

# ── Category → (color, style) ────────────────────────────────────────────────

_CATEGORY_RULES = [
    # Errors & warnings first (highest priority)
    (re.compile(r'\b(ERROR|EXCEPTION)\b',    re.I), SOFT_RED,    "bold"),
    (re.compile(r'\bWARNING\b',              re.I), SOFT_YELLOW, "bold"),
    # New block (most exciting event)
    (re.compile(r'\bUpdateTip\b'),                  NEON_GREEN,  "bold"),
    (re.compile(r'\breceived block\b',       re.I), SOFT_GREEN,  None),
    (re.compile(r'\bConnected to chain\b',   re.I), NEON_GREEN,  "bold"),
    # IBD / headers sync
    (re.compile(r'\bSynchroniz',             re.I), SOFT_YELLOW, None),
    (re.compile(r'\bpre-synchroniz',         re.I), SOFT_YELLOW, None),
    (re.compile(r'\bVerification progress\b',re.I), SOFT_YELLOW, None),
    # Network
    (re.compile(r'\b(net|net_processing|CConnman)\b'), CYAN, None),
    (re.compile(r'\breceived\b',             re.I), CYAN,        None),
    (re.compile(r'\bdisconnect\b',           re.I), SOFT_RED,    None),
    (re.compile(r'\bconnect\b',              re.I), SOFT_GREEN,  None),
    # Mempool
    (re.compile(r'\bmempool\b',              re.I), SOFT_YELLOW, None),
    (re.compile(r'\bAcceptToMemoryPool\b',   re.I), SOFT_YELLOW, None),
    # Wallet / RPC
    (re.compile(r'\bwallet\b',               re.I), PURPLE,      None),
    # Bitcoin script / consensus
    (re.compile(r'\bCoinBase\b|\bOP_\w+',    re.I), BTC_ORANGE,  None),
]


def _truncate_hash(h: str) -> str:
    """Shorten a hash to first-8…last-6 chars."""
    return f"{h[:8]}…{h[-6:]}"


def _format_line(raw: str) -> Text:
    """
    Parse one raw debug.log line into a styled Rich Text object.
    Each line fits on a single terminal row (long content is clipped).
    """
    t = Text(overflow="ellipsis", no_wrap=True)

    # ── 1. Strip and extract timestamp ───────────────────────────────────────
    m = _TS_RE.match(raw)
    if m:
        t.append(m.group(2), style=f"dim {DIM_BORDER}")   # HH:MM:SS only
        t.append("  ", style="default")
        body = raw[m.end():]
    else:
        body = raw.strip()

    # ── 2. Strip [category] prefix if present (common in newer core) ─────────
    cat_match = re.match(r'^\[([^\]]+)\]\s*', body)
    if cat_match:
        t.append(f"[{cat_match.group(1)}] ", style=CYAN)
        body = body[cat_match.end():]

    # ── 3. Choose line color based on content keywords ───────────────────────
    line_color  = "white"
    line_style  = None
    for pattern, color, style in _CATEGORY_RULES:
        if pattern.search(body):
            line_color = color
            line_style = style
            break

    # ── 4. Render body with inline substitutions ─────────────────────────────
    # We process the body token-by-token using a simple state machine to
    # avoid nested regex replacements corrupting the output.
    segments: list[tuple[str, str]] = []
    cursor = 0

    # Build an ordered list of all matches across multiple patterns
    matches: list[tuple[int, int, str, str]] = []   # start, end, text, highlight_color

    for pat, col, _ in [
        (_HASH64,  DIM_BORDER,  None),   # always dim full hashes
        (_HASH32,  DIM_BORDER,  None),
        (_IPv4,    CYAN,        None),
        (_ONION,   PURPLE,      None),
        (_PEER,    BTC_ORANGE,  None),
        (_HEIGHT,  BTC_ORANGE,  None),
    ]:
        for mm in pat.finditer(body):
            # Use group(1) if available (capture group), else full match
            start = mm.start(1) if mm.lastindex and mm.lastindex >= 1 else mm.start()
            end   = mm.end(1)   if mm.lastindex and mm.lastindex >= 1 else mm.end()
            raw_tok = mm.group(1) if mm.lastindex and mm.lastindex >= 1 else mm.group()
            # Truncate hashes
            if len(raw_tok) >= 40:
                display = _truncate_hash(raw_tok)
            else:
                display = raw_tok
            matches.append((start, end, display, col))

    # Sort and de-duplicate (keep first if overlapping)
    matches.sort(key=lambda x: x[0])
    deduped: list[tuple[int, int, str, str]] = []
    last_end = 0
    for sm in matches:
        if sm[0] >= last_end:
            deduped.append(sm)
            last_end = sm[1]

    # Build segment list
    for (start, end, display, col) in deduped:
        if cursor < start:
            segments.append((body[cursor:start], line_color))
        segments.append((display, col))
        cursor = end
    if cursor < len(body):
        segments.append((body[cursor:], line_color))

    full_style = f"bold {line_color}" if line_style == "bold" else line_color
    if not segments:
        t.append(body, style=full_style)
    else:
        for text, col in segments:
            style = f"bold {col}" if (line_style == "bold" and col == line_color) else col
            t.append(text, style=style)

    return t


# ── Screen ────────────────────────────────────────────────────────────────────

_LOG_HEADER_TEXT = " ₿  B I T C O I N   N O D E   L O G "

class _LogHeader(Static):
    def on_mount(self) -> None:
        t = Text(justify="center")
        t.append("  ₿  ", style=f"bold {BTC_ORANGE}")
        t.append(" debug.log  ", style="bold white")
        t.append("live tail", style=f"dim {NEON_GREEN}")
        t.append("  •  ", style=f"dim {DIM_BORDER}")
        t.append("L / Esc", style=f"dim {SOFT_YELLOW}")
        t.append(" → back", style="dim white")
        self.update(t)


class LogScreen(Screen):
    """Full-screen real-time debug.log viewer."""

    CSS = """
    Screen {
        background: #0a0a0a;
    }
    _LogHeader {
        height: 1;
        margin: 0 1 0 1;
        content-align: center middle;
    }
    #log-container {
        height: 1fr;
        border: solid #2a2a2a;
        margin: 0 1 0 1;
    }
    RichLog {
        background: #050505;
        padding: 0 1;
        scrollbar-color: #333333;
        scrollbar-background: #0a0a0a;
    }
    Footer {
        background: #111111;
    }
    """

    BINDINGS = [
        ("l",      "pop_screen", "Dashboard"),
        ("escape", "pop_screen", "Dashboard"),
        ("q",      "app.quit",   "Quit"),
        ("end",    "scroll_end", "Latest"),
        ("home",   "scroll_top", "Top"),
    ]

    def __init__(self, log_path: Optional[Path], **kwargs):
        super().__init__(**kwargs)
        self.log_path = log_path
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._INITIAL_LINES = 300     # lines to show on first open
        self._MAX_DISPLAY   = 2000    # RichLog buffer

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield _LogHeader()
        with Container(id="log-container"):
            yield RichLog(
                id="log",
                max_lines=self._MAX_DISPLAY,
                highlight=False,
                markup=False,
                auto_scroll=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Bitcoin Terminal — Log"
        log: RichLog = self.query_one("#log", RichLog)

        if not self.log_path:
            log.write(Text("  No log path configured.", style=f"dim {SOFT_YELLOW}"))
            return

        if not self.log_path.exists():
            log.write(Text(
                f"  debug.log not found:\n  {self.log_path}",
                style=f"dim {SOFT_RED}",
            ))
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._tail_worker, daemon=True
        )
        self._thread.start()

    def on_unmount(self) -> None:
        self._running = False

    # ── Background worker ────────────────────────────────────────────────────

    def _tail_worker(self) -> None:
        """Read the last N lines then stream new content."""
        log_path = self.log_path

        # --- seed: read last _INITIAL_LINES lines efficiently ----------------
        try:
            with open(log_path, "rb") as f:
                # Walk back to collect enough newlines
                f.seek(0, 2)
                file_size = f.tell()
                chunk_size = 65536
                buf = b""
                needed = self._INITIAL_LINES + 1
                pos = file_size

                while pos > 0 and buf.count(b"\n") < needed:
                    pos = max(pos - chunk_size, 0)
                    f.seek(pos)
                    buf = f.read(file_size - pos)

                lines = buf.decode("utf-8", errors="replace").splitlines()
                seed_lines = lines[-self._INITIAL_LINES:]
                tail_pos = file_size  # we'll continue from here

            # Push seed lines to the widget
            def _write_seed():
                if not self._running:
                    return
                widget: RichLog = self.query_one("#log", RichLog)
                for raw in seed_lines:
                    widget.write(_format_line(raw))
                widget.scroll_end(animate=False)

            self.call_from_thread(_write_seed)

        except (OSError, IOError):
            tail_pos = 0

        # --- live tail -------------------------------------------------------
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(tail_pos)
                while self._running:
                    batch: list[Text] = []
                    while True:
                        line = f.readline()
                        if not line:
                            break
                        raw = line.rstrip("\n")
                        if raw:
                            batch.append(_format_line(raw))

                    if batch and self._running:
                        captured = batch

                        def _write_batch(b=captured):
                            if not self._running:
                                return
                            try:
                                widget: RichLog = self.query_one(
                                    "#log", RichLog
                                )
                                for t in b:
                                    widget.write(t)
                            except Exception:
                                pass

                        self.call_from_thread(_write_batch)

                    time.sleep(0.25)

        except (OSError, IOError):
            pass

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_scroll_end(self) -> None:
        self.query_one("#log", RichLog).scroll_end(animate=True)

    def action_scroll_top(self) -> None:
        self.query_one("#log", RichLog).scroll_home(animate=True)
