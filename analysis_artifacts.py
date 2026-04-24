from pathlib import Path
import re


DATA_ROOT = Path("data")
DEFAULT_SYMBOL = "analysis"


def normalize_symbol(symbol: str | None) -> str:
    """Convert a symbol or display name into a filesystem-safe folder name."""
    raw_symbol = (symbol or "").strip()
    if not raw_symbol:
        return DEFAULT_SYMBOL
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_symbol)
    return normalized.strip("._") or DEFAULT_SYMBOL


def get_symbol_artifact_dir(symbol: str | None) -> Path:
    """Return the artifact directory for a symbol, creating it if needed."""
    artifact_dir = DATA_ROOT / normalize_symbol(symbol)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def get_analysis_artifact_paths(symbol: str | None) -> dict[str, Path]:
    """Return standard CSV and PNG artifact paths for an analysis run."""
    artifact_dir = get_symbol_artifact_dir(symbol)
    return {
        "directory": artifact_dir,
        "record_csv": artifact_dir / "record.csv",
        "kline_png": artifact_dir / "kline_chart.png",
        "trend_png": artifact_dir / "trend_graph.png",
    }