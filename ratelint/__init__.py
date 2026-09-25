"""Static checks for rate-limiting mistakes in Python source."""

from .checks import Finding, RuleConfig, check_source
from .config import load_config

__version__ = "0.1.0"
__all__ = ["Finding", "RuleConfig", "check_source", "load_config", "__version__"]
