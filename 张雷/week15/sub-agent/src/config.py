"""Central configuration. All thresholds tunable; defaults per spec/constitution v2.0.0."""
from dataclasses import dataclass


@dataclass
class Config:
    total_timeout: float = 300.0      # FR-010 global timeout (seconds)
    max_workers: int = 4              # FR-004 bounded ThreadPoolExecutor (I/O-bound, may exceed CPU)
    max_iterations: int = 5           # FR-011 ReAct runaway guard
    size_cap: int = 8192              # FR-016 result payload size cap (chars)
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    log_file: str = "logs/hydra.log"


CONFIG = Config()
