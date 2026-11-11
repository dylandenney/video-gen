import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)
