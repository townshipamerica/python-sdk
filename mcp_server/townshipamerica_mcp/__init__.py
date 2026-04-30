"""Model Context Protocol server for Township America.

Exposes PLSS conversion tools to AI agents (Claude, ChatGPT, Cursor, Copilot).

Tools:
    plss_to_coordinates: Convert a PLSS legal description to GPS coordinates.
    coordinates_to_plss: Reverse-lookup coordinates into a PLSS description.
    plss_to_geojson: Return the full section/quarter polygon as GeoJSON.
    validate_description: Check whether a PLSS string is valid and parseable.
    batch_convert: Process multiple descriptions in one call.

Run as:
    townshipamerica-mcp

Or as a Python module:
    python -m townshipamerica_mcp.server
"""

from .server import main

__version__ = "0.1.0"
__all__ = ["main"]
