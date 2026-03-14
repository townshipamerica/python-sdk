# Township America Python SDK

[![PyPI](https://img.shields.io/pypi/v/townshipamerica)](https://pypi.org/project/townshipamerica/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Convert US PLSS (Public Land Survey System) legal land descriptions to GPS coordinates and back. Covers all 30 PLSS states and 37 principal meridians.

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
| `search(location)`                                   | Convert PLSS description to GPS coordinates |
| `reverse(longitude, latitude, *, unit=None)`         | Find PLSS description at GPS coordinates    |
| `autocomplete(query, *, limit=None, proximity=None)` | Get search suggestions                      |
| `batch_search(locations)`                            | Batch convert up to 100 descriptions        |
| `batch_reverse(coordinates, *, unit=None)`           | Batch reverse geocode up to 100 points      |

All methods are also available on `AsyncTownshipAmerica` as async/await.

### Models

- **`FeatureCollection`** — GeoJSON response with `.centroid` and `.grid` helpers
- **`Feature`** — GeoJSON Feature with `.geometry` and `.properties`
- **`Point`** — GeoJSON Point with `.latitude` and `.longitude` properties
- **`AutocompleteResult`** — List of `.suggestions`

### Exceptions

| Exception              | HTTP Status | Description                |
| ---------------------- | ----------- | -------------------------- |
| `ValidationError`      | 400         | Invalid request parameters |
| `AuthenticationError`  | 401         | Missing or invalid API key |
| `NotFoundError`        | 404         | No results at coordinates  |
| `RateLimitError`       | 429         | Rate limit exceeded        |
| `PayloadTooLargeError` | 413         | Batch exceeds 100 items    |
| `ServerError`          | 5xx         | Server-side error          |

## Supported States

Alabama, Alaska, Arizona, Arkansas, California, Colorado, Florida, Idaho, Illinois, Indiana, Iowa, Kansas, Louisiana, Michigan, Minnesota, Mississippi, Missouri, Montana, Nebraska, Nevada, New Mexico, North Dakota, Ohio, Oklahoma, Oregon, South Dakota, Utah, Washington, Wisconsin, Wyoming.

## License

MIT — see [LICENSE](LICENSE) for details.

## Links

- [API Documentation](https://townshipamerica.com/api)
- [Get an API Key](https://townshipamerica.com/pricing)
- [Township America](https://townshipamerica.com)
