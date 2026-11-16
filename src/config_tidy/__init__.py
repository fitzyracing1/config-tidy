"""config-tidy: clean GitHub Actions workflow YAML without overwriting the input."""

from config_tidy.tidy import TidyResult, tidy

__version__ = "0.1.0"
__all__ = ["TidyResult", "tidy", "__version__"]
