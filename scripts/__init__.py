import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_os.environ.setdefault("PYTHONPYCACHEPREFIX", _os.path.join(_PROJECT_ROOT, ".cache"))
_sys.pycache_prefix = _os.environ["PYTHONPYCACHEPREFIX"]

from .bot import MihonoBourbot
from .models import GameScreen, Action
from .gui import main
