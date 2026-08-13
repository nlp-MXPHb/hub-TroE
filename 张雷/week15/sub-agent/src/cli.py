"""CLI entry point: run a research query through the main agent.

Usage:
  python src/cli.py "your research query" [--max-workers N]

Requires DEEPSEEK_API_KEY (or DASHSCOPE_API_KEY) in the environment and a real
web_search backend (replace default_backend in production).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # bare module imports from src/

from config import CONFIG
from llm_client import LLMClient
from main_agent import MainAgent
from tools.web_search import default_backend


def main():
    parser = argparse.ArgumentParser(description="Hydra parallel multi-subagent research agent")
    parser.add_argument("query", help="research query")
    parser.add_argument("--max-workers", type=int, default=CONFIG.max_workers)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or ""
    llm = LLMClient(api_key=api_key, base_url=CONFIG.llm_base_url, model=CONFIG.llm_model)
    agent = MainAgent(llm=llm, search_backend=default_backend,
                      config={"max_workers": args.max_workers})
    print(agent.run(args.query))


if __name__ == "__main__":
    main()
