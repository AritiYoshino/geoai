import json
import os
import sys
import traceback

from .config import ExperimentConfig
from .runner import run_experiment


def main():
    exp_id = sys.argv[1] if len(sys.argv) > 1 else "exp1"
    config_payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    config = ExperimentConfig(**config_payload)
    config.use_real_ace = False
    config.mock_mode = True
    os.environ.setdefault("GEOAI_REPORT_SKIP_CHARTS", "1")
    result = run_experiment(exp_id, config=config, app_state=None)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise SystemExit(1)
