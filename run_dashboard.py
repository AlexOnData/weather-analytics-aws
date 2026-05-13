"""Launch the Streamlit dashboard.

``python run_dashboard.py`` is equivalent to
``streamlit run dashboard/app.py``.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run", str(ROOT / "dashboard" / "app.py"),
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())
