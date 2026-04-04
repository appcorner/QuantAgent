import os

from dotenv import load_dotenv

load_dotenv(".env")

DEFAULT_CONFIG = {
    "agent_llm_model": os.environ.get("AGENT_LLM_MODEL", "gpt-5.4-mini"),
    "graph_llm_model": os.environ.get("GRAPH_LLM_MODEL", "gpt-5.4-mini"),
    "agent_llm_provider": "openai",  # "openai", "anthropic", or "qwen"
    "graph_llm_provider": "openai",  # "openai", "anthropic", or "qwen"
    "agent_llm_temperature": 0.1,
    "graph_llm_temperature": 0.1,
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "qwen_api_key": os.environ.get("DASHSCOPE_API_KEY", ""),
}
