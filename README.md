# Township America Python SDK

[![PyPI](https://img.shields.io/pypi/v/townshipamerica)](https://pypi.org/project/townshipamerica/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Convert US PLSS (Public Land Survey System) and Texas TXSS legal land descriptions to GPS coordinates and back. Covers all 30 PLSS states, 37 principal meridians, and all 254 Texas counties.

Built on official BLM GCDB data — the same source used by government agencies.

[Documentation](https://townshipamerica.com/api) · [GitHub](https://github.com/townshipamerica/python-sdk) · [PyPI](https://pypi.org/project/townshipamerica/)

## Installation

```bash
pip install townshipamerica
```

## Quick Start

```python
import os

from townshipamerica import TownshipAmerica

ta = TownshipAmerica(os.environ["TOWNSHIP_AMERICA_API_KEY"])

# Convert a PLSS description to GPS coordinates
result = ta.search("25 24N 1E 6th Meridian")
centroid = result.centroid
print(f"{centroid.geometry.latitude}, {centroid.geometry.longitude}")
# 41.077932, -104.01924

# Texas TXSS
tx = ta.search("A-175 Reeves County")
print(tx.centroid.properties.survey_system)  # TXSS
```

Get an API key at [townshipamerica.com/api](https://townshipamerica.com/api).

## Examples

### 1. Oil & Gas: Convert Well Locations to GPS

```python
from townshipamerica import TownshipAmerica

ta = TownshipAmerica("your_api_key")

well_locations = [
    "NE 7 102N 19W 5th Meridian",
    "SENE 22 3S 68W 6th Meridian",
    "NENE 12 4N 5E Indian Meridian",
]

# Batch convert all at once (up to 100 per request)
results = ta.batch_search(well_locations)

for fc in results:
    centroid = fc.centroid
    props = centroid.properties
    print(
        f"{props.legal_location} -> "
        f"{centroid.geometry.latitude:.6f}, {centroid.geometry.longitude:.6f} "
        f"({props.province})"
    )
```

### 2. GIS Pipeline: Reverse Geocode Field Coordinates

```python
from townshipamerica import TownshipAmerica

ta = TownshipAmerica("your_api_key")

# GPS coordinates from a field survey
field_points = [
    (-104.086743, 41.286021),
    (-104.011880, 41.336941),
    (-104.074171, 41.336931),
]

# Batch reverse geocode to PLSS descriptions
results = ta.batch_reverse(field_points, unit="Quarter Section")

for fc in results:
    centroid = fc.centroid
    if centroid:
        print(centroid.properties.legal_location)
```

### 3. Real Estate: Look Up a Single Parcel with GeoPandas

```python
import geopandas as gpd
from shapely.geometry import shape

from townshipamerica import TownshipAmerica

ta = TownshipAmerica("your_api_key")

result = ta.search("14 5N 3W 6th Meridian")

# Convert the grid boundary to a Shapely geometry
grid_feature = result.grid
geometry = shape(grid_feature.geometry.model_dump())

# Build a GeoDataFrame for spatial analysis
gdf = gpd.GeoDataFrame(
    [{"legal_location": grid_feature.properties.legal_location,
      "state": grid_feature.properties.province}],
    geometry=[geometry],
    crs="EPSG:4326",
)

print(gdf)
# Export to file
# gdf.to_file("parcel.geojson", driver="GeoJSON")
```

## Parcel Reports

v2.0.0 adds the Energy, Federal Land, and Texas report APIs:

```python
from townshipamerica import TownshipAmerica

ta = TownshipAmerica("your_api_key")

# Energy report for a PLSS section — wells, operators, federal leases,
# county royalties, orphaned wells, pipelines, FracFocus, constraints
energy = ta.energy_report("25 24N 1E 6th Meridian")
print(energy.summary.wells_in_section)
print(energy.wells.in_section.rows[0].api_number)

# Only the sections you need — the rest are never queried
slim = ta.energy_report("25 24N 1E 6th Meridian", include=["wells", "pipelines"])

# Federal-land report — surface management, BLM leases/ROWs, flood zones,
# mining claims, wetlands, soils, crop history, wildfire risk, elevation...
federal = ta.federal_land_report("NW 25 24N 1E 6th Meridian")
print(federal.surface_management.rows[0].agency)

# Texas abstract report — GLO leases/units, PSF lands, RRC wells and
# pipelines, permits, coastal erosion, federal overlays, RRC production
texas = ta.texas_report("A-175 Reeves County")
print(texas.production.summary.total_cum_boe)

# RRC lease production by legal description or registry keys
production = ta.texas_production("A-175 Reeves County")
production = ta.texas_production(county_fips="48389", abstract_no="175")

# Per-well allocated production + Arps decline fit (API-8 or API-14)
well = ta.texas_well("42-389-32345")
if well.decline.available:
    print(well.decline.value.di)
```

Array sections are `{total, returned, truncated, more, rows}` envelopes; a
failed section lands in `meta.unavailable` instead of failing the report.
Pass `include=["geometry", ...]` to attach the parcel boundary under
`parcel.geometry`. Texas volumes are allocated estimates — RRC reports
production by lease, never by well.

## Async Support

```python
import asyncio
from townshipamerica import AsyncTownshipAmerica

async def main():
    async with AsyncTownshipAmerica("your_api_key") as ta:
        result = await ta.search("25 24N 1E 6th Meridian")
        print(result.centroid.geometry.latitude)

asyncio.run(main())
```

## API Reference

### `TownshipAmerica(api_key, *, base_url=..., timeout=30.0)`

| Method                                               | Description                                 |
| ---------------------------------------------------- | ------------------------------------------- |
| `search(location)`                                   | Convert PLSS or TXSS description to GPS     |
| `reverse(longitude, latitude, *, unit=None)`         | Find legal description at GPS coordinates   |
| `autocomplete(query, *, limit=None, proximity=None)` | Get search suggestions                      |
| `batch_search(locations)`                            | Batch convert up to 100 descriptions        |
| `batch_reverse(coordinates, *, unit=None)`           | Batch reverse geocode up to 100 points      |
| `energy_report(legal_location, *, include=None)`     | Energy parcel report (PLSS)                 |
| `federal_land_report(legal_location, *, include=None)` | Federal-land parcel report (PLSS)         |
| `texas_report(legal_location, *, include=None)`      | Texas abstract report (TXSS)                |
| `texas_production(legal_location=None, *, county_fips=None, abstract_no=None, block_no=None)` | RRC lease production for an abstract |
| `texas_well(api)`                                    | Per-well allocated production + decline fit |

All methods are also available on `AsyncTownshipAmerica` as async/await.

### Models

- **`FeatureCollection`** — GeoJSON response with `.centroid` and `.grid` helpers
- **`Feature`** — GeoJSON Feature with `.geometry` and `.properties`
- **`Point`**, **`Polygon`**, **`MultiPolygon`** — GeoJSON geometry types
- **`EnergyReport`**, **`FederalLandReport`**, **`TexasReport`** — typed parcel reports
- **`TexasProduction`**, **`TexasWell`** — RRC production rollups and per-well analytics
- **`SectionEnvelope`** — `{total, returned, truncated, more, rows}` array sections
- **`ReportMeta`** — `meta.unavailable` degraded-section list + per-section sources

### Exceptions

| Exception              | HTTP Status | Description                |
| ---------------------- | ----------- | -------------------------- |
| `ValidationError`      | 400         | Invalid request parameters |
| `AuthenticationError`  | 401         | Missing or invalid API key |
| `NotFoundError`        | 404         | No results at coordinates  |
| `RateLimitError`       | 429         | Rate limit exceeded        |
| `PayloadTooLargeError` | 413         | Batch exceeds 100 items    |
| `ServerError`          | 5xx         | Server-side error          |

Errors from the Energy, Federal Land, and Texas APIs also carry a
machine-readable `.code` (e.g. `invalid_parameter`, `plss_not_supported`,
`ambiguous_location`, `not_found`, `rate_limit_exceeded`); it is `None` for
endpoints that do not send one.

### What's new in v2.0.0

- New methods on both clients: `energy_report`, `federal_land_report`,
  `texas_report`, `texas_production`, `texas_well` (sync and async).
- New pydantic models for the reports, re-exported from `townshipamerica`.
- Exceptions gained a `code` attribute; v1 error bodies of the form
  `{"error": {"code", "message"}}` are now parsed into `.message`/`.code`.
  If you construct SDK exceptions directly with positional arguments,
  note the added keyword parameter.

## Supported Coverage

**PLSS:** Alabama, Alaska, Arizona, Arkansas, California, Colorado, Florida, Idaho, Illinois, Indiana, Iowa, Kansas, Louisiana, Michigan, Minnesota, Mississippi, Missouri, Montana, Nebraska, Nevada, New Mexico, North Dakota, Ohio, Oklahoma, Oregon, South Dakota, Utah, Washington, Wisconsin, Wyoming.

**Texas TXSS:** All 254 counties — abstract, block/section, and survey descriptions.

## License

MIT — see [LICENSE](LICENSE) for details.

## MCP (AI agents)

For Claude Desktop, Cursor, and other MCP clients, use the separate [python-mcp](https://github.com/townshipamerica/python-mcp) package:

```bash
pip install townshipamerica-mcp
```

See [python-mcp](https://github.com/townshipamerica/python-mcp) for setup and tool documentation.

## Links

- [API Documentation](https://townshipamerica.com/api)
- [MCP server (python-mcp)](https://github.com/townshipamerica/python-mcp)
- [Get an API Key](https://townshipamerica.com/pricing)
- [Township America](https://townshipamerica.com)
