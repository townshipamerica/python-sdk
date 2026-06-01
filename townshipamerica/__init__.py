"""Township America Python SDK — PLSS and Texas TXSS coordinate conversion.

Usage::

    from townshipamerica import TownshipAmerica

    ta = TownshipAmerica("your_api_key")
    result = ta.search("NW 25 24N 1E 6th Meridian")
    centroid = result.centroid
    print(centroid.geometry.latitude, centroid.geometry.longitude)
"""

from .client import AsyncTownshipAmerica, TownshipAmerica
from .exceptions import (
    AuthenticationError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
    TownshipAmericaError,
    ValidationError,
)
from .models import (
    Feature,
    FeatureCollection,
    FeatureProperties,
    MultiPolygon,
    Point,
    Polygon,
)

__all__ = [
    "TownshipAmerica",
    "AsyncTownshipAmerica",
    "TownshipAmericaError",
    "AuthenticationError",
    "NotFoundError",
    "PayloadTooLargeError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "FeatureCollection",
    "Feature",
    "FeatureProperties",
    "Point",
    "Polygon",
    "MultiPolygon",
]

from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("townshipamerica")
except Exception:
    __version__ = "0.1.0"
