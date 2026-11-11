import json
import sys
from pathlib import Path


def main(paths: list[str]) -> None:
    reports = [
        (Path(p).stem, json.loads(Path(p).read_text(encoding="utf-8")))
        for p in paths
    ]
    keys = list(reports[0][1]["aggregate"])
    print(f"{'metric':<14}" + "".join(f"{name:>26}" for name, _ in reports))
    for k in keys:
        row = "".join(
            f"{r['aggregate'].get(k, float('nan')):>26.4f}" for _, r in reports
        )
        print(f"{k:<14}{row}")


if __name__ == "__main__":
    main(sys.argv[1:])
