"""orgcore — shared logic for the hermes-organization-layer plugin.

Pure stdlib (cross-platform: Windows / macOS / Linux). No third-party deps.
"""

from . import config
from . import workspace
from . import index
from . import actions

__all__ = ["config", "workspace", "index", "actions"]
__version__ = "0.1.0"