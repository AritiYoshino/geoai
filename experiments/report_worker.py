import json
import os
import sys
import traceback

from .reporting import generate_report
from .runner import get_result


def main():
    result_id = sys.argv[1] if len(sys.argv) > 1 else "exp1"
    include_ai_summary = bool(int(sys.argv[2])) if len(sys.argv) > 2 else False
    if len(sys.argv) > 3 and sys.argv[3] == "--skip-charts":
        os.environ["GEOAI_REPORT_SKIP_CHARTS"] = "1"
    report = generate_report(get_result(result_id), include_ai_summary=include_ai_summary)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise SystemExit(1)
