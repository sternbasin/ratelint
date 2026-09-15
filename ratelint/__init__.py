"""Static checks for rate-limiting mistakes in Python source."""

from .checks import Finding, check_source

__version__ = "0.1.0"
__all__ = ["Finding", "check_source", "__version__"]
