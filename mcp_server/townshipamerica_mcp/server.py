"""MCP server exposing Township America PLSS tools to AI agents."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from townshipamerica import AsyncTownshipAmerica
from townshipamerica.exceptions import TownshipAmericaError

logger = logging.getLogger("townshipamerica_mcp")

server: Server = Server("townshipamerica")

API_KEY_ENV = "TOWNSHIP_AMERICA_API_KEY"
BASE_URL_ENV = "TOWNSHIP_AMERICA_BASE_URL"


def _get_api_key() -> str:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"Set the {API_KEY_ENV} environment variable to your Township America API key. "
            "Get one at https://townshipamerica.com/api."
        )
    return key


def _make_client() -> AsyncTownshipAmerica:
    base_url = os.environ.get(BASE_URL_ENV)
    kwargs: dict[str, Any] = {"api_key": _get_api_key()}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncTownshipAmerica(**kwargs)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the tool catalog visible to AI agents."""
    return [
        Tool(
            name="plss_to_coordinates",
            description=(
                "Convert a Public Land Survey System (PLSS) legal description to GPS coordinates "
                "(latitude/longitude). Accepts descriptions for all 30 PLSS states and 37 "
                "principal meridians. Examples: 'NW 25 24N 1E 6th Meridian', "
                "'NE 12 4N 5E Indian Meridian', 'SE¼ NW¼ Section 14 T2N R4E Mount Diablo Meridian'. "
                "Returns the section centroid and bounding polygon."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "PLSS legal land description (any common format).",
                    }
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="coordinates_to_plss",
            description=(
                "Reverse-lookup GPS coordinates (latitude/longitude) to a PLSS legal description. "
                "Returns the section, township, range, and principal meridian for the parcel "
                "containing the point."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude in decimal degrees."},
                    "lon": {"type": "number", "description": "Longitude in decimal degrees."},
                },
                "required": ["lat", "lon"],
            },
        ),
        Tool(
            name="plss_to_geojson",
            description=(
                "Return the full section, quarter-section, or aliquot-part boundary polygon for a "
                "PLSS legal description as a GeoJSON FeatureCollection. Useful when an AI agent "
                "needs to plot the parcel on a map or perform spatial analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "PLSS legal land description.",
                    }
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="validate_description",
            description=(
                "Check whether a PLSS legal description is valid and parseable. Returns "
                "{valid: true/false, normalized: '...', state: '...', meridian: '...', reason: '...'}. "
                "Useful for sanity-checking user input before downstream processing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "PLSS legal land description to validate.",
                    }
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="batch_convert",
            description=(
                "Convert multiple PLSS descriptions to coordinates in one call. Accepts up to 100 "
                "descriptions per request. Returns an array of results matching the input order."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "descriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of PLSS legal land descriptions.",
                        "maxItems": 100,
                    }
                },
                "required": ["descriptions"],
            },
        ),
        Tool(
            name="autocomplete",
            description=(
                "Get autocomplete suggestions for a partial PLSS description (e.g., user typing "
                "'T2N R4'). Returns up to 10 candidate descriptions ordered by likelihood."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Partial PLSS description.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum suggestions (default 10, max 25).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


def _ok(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str, indent=2))]


def _err(message: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": message}, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        async with _make_client() as client:
            if name == "plss_to_coordinates":
                description = arguments["description"]
                result = await client.search(description)
                payload = result.model_dump() if hasattr(result, "model_dump") else result
                return _ok(_summarize_search(payload, description))

            if name == "coordinates_to_plss":
                lat = float(arguments["lat"])
                lon = float(arguments["lon"])
                result = await client.reverse(lat=lat, lon=lon)
                payload = result.model_dump() if hasattr(result, "model_dump") else result
                return _ok(payload)

            if name == "plss_to_geojson":
                description = arguments["description"]
                result = await client.search(description)
                payload = result.model_dump() if hasattr(result, "model_dump") else result
                return _ok(payload)

            if name == "validate_description":
                description = arguments["description"]
                try:
                    result = await client.search(description)
                    payload = result.model_dump() if hasattr(result, "model_dump") else result
                    feature = (payload.get("features") or [{}])[0]
                    props = feature.get("properties", {}) if isinstance(feature, dict) else {}
                    return _ok(
                        {
                            "valid": True,
                            "input": description,
                            "normalized": props.get("legal_location"),
                            "state": props.get("state"),
                            "meridian": props.get("meridian"),
                        }
                    )
                except TownshipAmericaError as exc:
                    return _ok({"valid": False, "input": description, "reason": str(exc)})

            if name == "batch_convert":
                descriptions = arguments.get("descriptions", [])
                if not isinstance(descriptions, list) or not descriptions:
                    return _err("descriptions must be a non-empty array of strings")
                results = await client.batch_search(descriptions)
                payload = (
                    [r.model_dump() if hasattr(r, "model_dump") else r for r in results]
                    if isinstance(results, list)
                    else results
                )
                return _ok(payload)

            if name == "autocomplete":
                query = arguments["query"]
                limit = int(arguments.get("limit", 10))
                results = await client.autocomplete(query, limit=limit)
                payload = (
                    [r.model_dump() if hasattr(r, "model_dump") else r for r in results]
                    if isinstance(results, list)
                    else results
                )
                return _ok(payload)

            return _err(f"Unknown tool: {name}")

    except TownshipAmericaError as exc:
        logger.exception("Township America API error")
        return _err(f"API error: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in tool %s", name)
        return _err(f"Unexpected error: {exc}")


def _summarize_search(payload: dict[str, Any], original: str) -> dict[str, Any]:
    """Pull the highest-signal fields out of the GeoJSON for AI consumption."""
    if not isinstance(payload, dict):
        return {"input": original, "raw": payload}
    features = payload.get("features") or []
    if not features:
        return {"input": original, "found": False, "raw": payload}
    first = features[0] if isinstance(features[0], dict) else {}
    props = first.get("properties", {}) if isinstance(first, dict) else {}
    geometry = first.get("geometry") if isinstance(first, dict) else None
    centroid = None
    if geometry and geometry.get("type") in ("Point",):
        centroid = geometry.get("coordinates")
    return {
        "input": original,
        "found": True,
        "legal_location": props.get("legal_location"),
        "state": props.get("state"),
        "county": props.get("county"),
        "meridian": props.get("meridian"),
        "centroid": centroid,
        "geojson": payload,
    }


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for the `townshipamerica-mcp` console script."""
    logging.basicConfig(
        level=os.environ.get("MCP_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
