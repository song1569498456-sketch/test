from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class JsonlLogger:
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = self.log_dir / f"{day}.jsonl"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
