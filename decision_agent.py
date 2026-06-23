"""
Agent for making final trade decisions in high-frequency trading (HFT) context.
Combines indicator, pattern, and trend reports to issue a LONG or SHORT order.
Now enhanced with historical performance learning.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from performance_tracker import PerformanceTracker
    LEARNING_ENABLED = True
except ImportError:
    LEARNING_ENABLED = False


SOURCE_BASE_DIR = Path(__file__).resolve().parent
RUNTIME_BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_BASE_DIR
DEFAULT_DECISION_PROMPT_NAME = "decision_agent_prompt_default.md"


def _candidate_base_dirs() -> list[Path]:
    candidates = [RUNTIME_BASE_DIR, Path.cwd(), SOURCE_BASE_DIR]
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _load_env_files() -> None:
    for base_dir in _candidate_base_dirs():
        env_file = base_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)


def _resolve_relative_path(path_text: str) -> Path:
    raw_path = Path(path_text)
    if raw_path.is_absolute():
        return raw_path

    for base_dir in _candidate_base_dirs():
        candidate = base_dir / raw_path
        if candidate.exists():
            return candidate

    return RUNTIME_BASE_DIR / raw_path


def _default_prompt_path() -> Path:
    return _resolve_relative_path(DEFAULT_DECISION_PROMPT_NAME)


_load_env_files()


def _read_decision_prompt_template() -> str:
    configured_prompt_file = os.environ.get("DECISION_AGENT_PROMPT", "").strip()

    if configured_prompt_file:
        prompt_path = _resolve_relative_path(configured_prompt_file)
    else:
        prompt_path = _default_prompt_path()

    default_prompt_path = _default_prompt_path()

    print(f"Using decision prompt template: {prompt_path}")

    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    if default_prompt_path.exists():
        return default_prompt_path.read_text(encoding="utf-8")

    return (
        "You are a high-frequency quantitative trading (HFT) analyst operating on the current "
        "{time_frame} K-line chart for {stock_name}. Your task is to issue an immediate "
        "execution order: LONG or SHORT. HOLD is prohibited.\n\n"
        "Technical Indicator Report:\n{indicator_report}\n\n"
        "Pattern Report:\n{pattern_report}\n\n"
        "Trend Report:\n{trend_report}\n"
    )


def _get_learning_context(symbol: str, timeframe: str, min_trades: int = 10) -> str:
    """
    Get historical performance learning context for the decision prompt.

    Returns empty string if learning is disabled or insufficient data.
    """
    if not LEARNING_ENABLED:
        return ""

    try:
        tracker = PerformanceTracker()

        # Check if we have enough trades
        recent_trades = tracker.get_recent_trades(symbol=symbol, timeframe=timeframe, limit=100)
        if len(recent_trades) < min_trades:
            return ""

        # Generate learning report
        learning_report = tracker.generate_learning_report(
            symbol=symbol,
            timeframe=timeframe,
            limit=50
        )

        # Wrap in clear section
        return f"""

---
## 📚 Historical Performance Context (Learning System)

{learning_report}

**IMPORTANT**: Use these insights to improve your decision quality. Avoid patterns/conditions that historically underperform.
---
"""
    except Exception as e:
        print(f"Warning: Could not load learning context: {e}")
        return ""


def _ensure_required_report_placeholders(template: str) -> str:
    required_sections = [
        ("indicator_report", "**Technical Indicator Report**\n{indicator_report}"),
        ("pattern_report", "**Pattern Report**\n{pattern_report}"),
        ("trend_report", "**Trend Report**\n{trend_report}"),
    ]

    missing_sections = [
        section_text
        for placeholder, section_text in required_sections
        if f"{{{placeholder}}}" not in template
    ]

    if not missing_sections:
        return template

    return template.rstrip() + "\n\n" + "\n\n".join(missing_sections)


def _render_prompt_template(template: str, values: dict) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))

    # Support templates originally written for f-strings with escaped braces.
    return rendered.replace("{{", "{").replace("}}", "}")


def create_final_trade_decider(llm):
    """
    Create a trade decision agent node. The agent uses LLM to synthesize indicator, pattern, and trend reports
    and outputs a final trade decision (LONG or SHORT) with justification and risk-reward ratio.
    """

    def trade_decision_node(state) -> dict:
        indicator_report = state["indicator_report"]
        pattern_report = state["pattern_report"]
        trend_report = state["trend_report"]
        time_frame = state["time_frame"]
        stock_name = state["stock_name"]
        market = state.get("market", "")

        # --- Load historical learning context ---
        use_learning = os.environ.get("USE_LEARNING", "true").lower() in ("true", "1", "yes")
        learning_context = ""

        if use_learning and LEARNING_ENABLED:
            learning_context = _get_learning_context(
                symbol=stock_name,
                timeframe=time_frame,
                min_trades=int(os.environ.get("MIN_LEARNING_TRADES", "10"))
            )
            if learning_context:
                print(f"✓ Learning context loaded for {stock_name} {time_frame}")
            else:
                print(f"○ Insufficient data for learning context ({stock_name} {time_frame})")

        # --- System prompt for LLM ---
        prompt_template = _read_decision_prompt_template()
        prompt_template = _ensure_required_report_placeholders(prompt_template)

        # Inject learning context before reports
        if learning_context:
            prompt_template = prompt_template + learning_context

        prompt = _render_prompt_template(
            prompt_template,
            {
                "indicator_report": indicator_report,
                "pattern_report": pattern_report,
                "trend_report": trend_report,
                "time_frame": time_frame,
                "timeframe": time_frame,
                "stock_name": stock_name,
                "symbol": stock_name,
                "market": market,
            },
        )

        # --- LLM call for decision ---
        response = llm.invoke(prompt)

        return {
            "final_trade_decision": response.content,
            "messages": [response],
            "decision_prompt": prompt,
        }

    return trade_decision_node
