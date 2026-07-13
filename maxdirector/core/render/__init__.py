"""Render backend planning — PURE. Turns a plan's render spec into concrete per-shot jobs
and, for Vantage, the exact ``vantage_console`` command lines (the sequential batch). The
actual pymxs render / subprocess execution lives in ``maxdirector.maxbridge``."""

from .backend import RenderJob, plan_jobs  # noqa: F401
from .vantage import vantage_commands       # noqa: F401
