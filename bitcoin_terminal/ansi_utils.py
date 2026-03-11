"""
ANSI Terminal Utilities
Minimalistic BBS-style terminal helpers inspired by retro aesthetics
"""


# Simple color palette - minimalistic BBS style
def success(text: str) -> str:
    """Green text for success/positive values"""
    return f"[green]{text}[/green]"


def warning(text: str) -> str:
    """Yellow text for warnings"""
    return f"[yellow]{text}[/yellow]"


def muted(text: str) -> str:
    """Dim text for less important info"""
    return f"[dim]{text}[/dim]"


def bold(text: str) -> str:
    """Bold white text for headers"""
    return f"[bold white]{text}[/bold white]"


def jformat(value, decimals=2) -> str:
    """Format numbers with commas. Returns '0' for zero, '-' for None."""
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        if decimals == 0:
            return f"{int(value):,}"
        return f"{value:,.{decimals}f}"
    return str(value)


def format_bytes(bytes_val) -> str:
    """Format bytes into human-readable string"""
    if not bytes_val:
        return "0 B"
    if bytes_val < 1024:
        return f"{bytes_val:.2f} B" if isinstance(bytes_val, float) else f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val/1024:.1f} KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val/(1024**2):.1f} MB"
    else:
        return f"{bytes_val/(1024**3):.2f} GB"


def format_uptime(seconds: int) -> str:
    """Format uptime seconds into readable string"""
    if not seconds or seconds < 0:
        return "-"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
