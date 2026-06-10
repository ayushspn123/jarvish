"""Tool package. Importing it registers every tool with the registry."""

from . import desktop, files, gcal, google, system, web  # noqa: F401  (side-effect imports)
from .registry import call_tool, get_schemas

__all__ = ["call_tool", "get_schemas"]
