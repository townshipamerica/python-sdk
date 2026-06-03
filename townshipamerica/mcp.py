"""MCP (Model Context Protocol) server for Township America PLSS conversion.

Exposes PLSS coordinate conversion tools to any MCP-compatible AI agent
(Claude, ChatGPT, custom agents). Wraps the Township America REST API.

Usage::

    # Set your API key
    export TOWNSHIP_AMERICA_API_KEY=your_key

    # Run the server (stdio transport for MCP clients)
    townshipamerica-mcp
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import TownshipAmerica
from .exceptions import TownshipAmericaError

mcp = FastMCP(
    "Township America PLSS",
    instructions=(
        "Convert US Public Land Survey System (PLSS) legal land descriptions "
        "to GPS coordinates and back. Covers all 30 PLSS states and 37 principal "
        "meridians. Built on official BLM GCDB survey data."
    ),
)


def _get_client() -> TownshipAmerica:
    """Create a Township America client from the environment API key."""
    api_key = os.environ.get("TOWNSHIP_AMERICA_API_KEY", "")
    if not api_key:
        raise ValueError(
            "TOWNSHIP_AMERICA_API_KEY environment variable is required. "
            "Get a key at https://townshipamerica.com/pricing"
        )
    return TownshipAmerica(api_key)


def _feature_collection_to_dict(fc: Any) -> dict:
    """Convert a FeatureCollection to a plain dict for MCP responses."""
    return fc.model_dump()


@mcp.tool()
def plss_to_latlon(location: str) -> dict:
    """Convert a PLSS legal land description to GPS coordinates.

    Takes a PLSS description like "NW 25 24N 1E 6th Meridian" or
    "SENE 22 3S 68W 6th Meridian" and returns the GPS coordinates
    (latitude/longitude) along with the section boundary polygon.

    Supports all 30 PLSS states, 37 principal meridians, and aliquot
    parts down to 1/256th section. Uses official BLM GCDB survey data.

    Args:
        location: A PLSS legal land description. Examples:
            - "NW 25 24N 1E 6th Meridian"
            - "SENE 22 3S 68W 6th Meridian"
            - "14 5N 3W 6th Meridian"
            - "NE 12 4N 5E Indian Meridian"

    Returns:
        GeoJSON FeatureCollection with centroid point and grid boundary polygon.
    """
    client = _get_client()
    try:
        result = client.search(location)
        return _feature_collection_to_dict(result)
    except TownshipAmericaError as e:
        return {"error": e.message, "status_code": e.status_code}
    finally:
        client.close()


@mcp.tool()
def latlon_to_plss(
    latitude: float,
    longitude: float,
    unit: str = "Quarter Section",
) -> dict:
    """Convert GPS coordinates to a PLSS legal land description.

    Takes a latitude/longitude pair and returns the PLSS description
    (township, range, section, quarter) at that location.

    Args:
        latitude: Latitude (y) coordinate. Example: 41.077932
        longitude: Longitude (x) coordinate. Example: -104.01924
        unit: Precision level for the result. Options:
            - "Township" — township level only
            - "First Division" — section level
            - "Quarter Section" — quarter section (default)
            - "all" — all available levels

    Returns:
        GeoJSON FeatureCollection with the PLSS description at those coordinates.
    """
    client = _get_client()
    try:
        result = client.reverse(longitude, latitude, unit=unit)
        return _feature_collection_to_dict(result)
    except TownshipAmericaError as e:
        return {"error": e.message, "status_code": e.status_code}
    finally:
        client.close()


@mcp.tool()
def batch_plss_convert(locations: list[str]) -> dict:
    """Convert multiple PLSS descriptions to GPS coordinates in one call.

    Batch-converts up to 100 PLSS legal land descriptions to GPS
    coordinates. More efficient than calling plss_to_latlon repeatedly.

    Args:
        locations: List of PLSS legal land descriptions (max 100). Examples:
            ["NE 7 102N 19W 5th Meridian", "SENE 22 3S 68W 6th Meridian"]

    Returns:
        Dictionary with "results" key containing a list of GeoJSON
        FeatureCollections (or null for unresolvable descriptions).
    """
    if len(locations) > 100:
        return {"error": "Maximum 100 locations per batch request", "status_code": 413}

    client = _get_client()
    try:
        results = client.batch_search(locations)
        return {
            "results": [
                _feature_collection_to_dict(fc) if fc is not None else None
                for fc in results
            ]
        }
    except TownshipAmericaError as e:
        return {"error": e.message, "status_code": e.status_code}
    finally:
        client.close()


def main() -> None:
    """Run the MCP server with stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
