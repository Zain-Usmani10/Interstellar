"""Set BRAIN_REFERENCE_ROOT to a read-only checkout when core PRs are unmerged."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
REFERENCE = Path(os.environ.get("BRAIN_REFERENCE_ROOT", ROOT)).resolve()
sys.path.append(str(REFERENCE))
import app
if str(REFERENCE / "app") not in app.__path__:
    app.__path__.append(str(REFERENCE / "app"))
