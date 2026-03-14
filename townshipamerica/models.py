"""Pydantic models for Township America API request and response types."""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- GeoJSON Models ---


class Point(BaseModel):
    """GeoJSON Point geometry."""

    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(
        ..., description="[longitude, latitude] or [longitude, latitude, altitude]", min_length=2, max_length=3
    )

    @property
    def longitude(self) -> float:
        """Longitude (x) coordinate."""
        return self.coordinates[0]

    @property
    def latitude(self) -> float:
        """Latitude (y) coordinate."""
        return self.coordinates[1]


class Polygon(BaseModel):
    """GeoJSON Polygon geometry."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]] = Field(
        ..., description="Array of linear rings"
    )


class FeatureProperties(BaseModel):
    """Properties attached to each GeoJSON Feature returned by the API."""

    shape: Optional[Literal["grid", "centroid"]] = None
    search_term: Optional[str] = None
    legal_location: Optional[str] = None
    alternate_legal_location: Optional[str] = None
    unit: Optional[str] = None
    survey_system: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = Field(None, description="US state name")


class Feature(BaseModel):
    """GeoJSON Feature with Township America properties."""

    type: Literal["Feature"] = "Feature"
    geometry: Union[Point, Polygon] = Field(
        ..., discriminator="type"
    )
    properties: FeatureProperties = Field(default_factory=FeatureProperties)


class FeatureCollection(BaseModel):
    """GeoJSON FeatureCollection returned by Township America API endpoints."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[Feature] = Field(default_factory=list)

    @property
    def centroid(self) -> Optional[Feature]:
        """Return the centroid feature, if present."""
        for f in self.features:
            if f.properties.shape == "centroid":
                return f
        return None

    @property
    def grid(self) -> Optional[Feature]:
        """Return the grid (boundary) feature, if present."""
        for f in self.features:
            if f.properties.shape == "grid":
                return f
        return None
