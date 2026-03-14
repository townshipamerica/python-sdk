"""Synchronous and asynchronous clients for the Township America API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import httpx

from .exceptions import (
    AuthenticationError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
    TownshipAmericaError,
    ValidationError,
)
from .models import FeatureCollection

BASE_URL = "https://developer.townshipamerica.com"


def _raise_for_status(response: httpx.Response) -> None:
    """Translate HTTP error responses into typed exceptions."""
    if response.is_success:
        return

    try:
        body = response.json()
        message = body.get("message", response.text)
    except Exception:
        message = response.text

    status = response.status_code
    if status == 400:
        raise ValidationError(message, status_code=status)
    if status == 401:
        raise AuthenticationError(message, status_code=status)
    if status == 404:
        raise NotFoundError(message, status_code=status)
    if status == 413:
        raise PayloadTooLargeError(message, status_code=status)
    if status == 429:
        retry_after_raw = response.headers.get("retry-after")
        retry_after = float(retry_after_raw) if retry_after_raw else None
        raise RateLimitError(message, status_code=status, retry_after=retry_after)
    if status >= 500:
        raise ServerError(message, status_code=status)
    raise TownshipAmericaError(message, status_code=status)


class TownshipAmerica:
    """Synchronous client for the Township America API.

    Args:
        api_key: Your Township America API key.
        base_url: Override the default API base URL.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS to protect your API key in transit")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"X-API-Key": api_key, "User-Agent": "townshipamerica-python/0.1.0"},
            timeout=timeout,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "TownshipAmerica":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- Search ---

    def search(self, location: str) -> FeatureCollection:
        """Convert a PLSS legal land description to GPS coordinates.

        Args:
            location: A PLSS legal land description, e.g.
                ``"NW 25 24N 1E 6th Meridian"`` or ``"NE 12 4N 5E Indian Meridian"``.

        Returns:
            A GeoJSON FeatureCollection containing the grid boundary and centroid.

        Raises:
            ValidationError: If the location string is invalid.
            AuthenticationError: If the API key is missing or invalid.
            RateLimitError: If the rate limit is exceeded.
        """
        response = self._client.get(
            "/search/legal-location", params={"location": location}
        )
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    def reverse(
        self,
        longitude: float,
        latitude: float,
        *,
        unit: Optional[str] = None,
    ) -> FeatureCollection:
        """Find the PLSS legal land description at the given GPS coordinates.

        Args:
            longitude: Longitude (x) coordinate.
            latitude: Latitude (y) coordinate.
            unit: Precision level — ``"Township"``, ``"First Division"``,
                ``"Second Division"``, or ``"all"``.

        Returns:
            A GeoJSON FeatureCollection with the matching land description.

        Raises:
            NotFoundError: If no land description exists at those coordinates.
        """
        params: Dict[str, str] = {"location": f"{longitude},{latitude}"}
        if unit is not None:
            params["unit"] = unit
        response = self._client.get("/search/coordinates", params=params)
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    # --- Autocomplete ---

    def autocomplete(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        proximity: Optional[tuple[float, float]] = None,
    ) -> FeatureCollection:
        """Get autocomplete suggestions for a partial PLSS description.

        Args:
            query: Partial search query (minimum 2 characters).
            limit: Maximum number of suggestions (1–10, default 3).
            proximity: ``(longitude, latitude)`` tuple to bias results.

        Returns:
            A GeoJSON FeatureCollection containing matching suggestions.
        """
        params: Dict[str, Union[str, int]] = {"location": query}
        if limit is not None:
            params["limit"] = limit
        if proximity is not None:
            params["proximity"] = f"{proximity[0]},{proximity[1]}"
        response = self._client.get(
            "/autocomplete/legal-location", params=params
        )
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    # --- Batch ---

    def batch_search(
        self, locations: List[str]
    ) -> List[Optional[FeatureCollection]]:
        """Convert multiple PLSS descriptions to GPS coordinates in one request.

        Args:
            locations: List of PLSS legal land descriptions (max 100).

        Returns:
            A list of GeoJSON FeatureCollections (or None for no-match entries),
            one per input location.

        Raises:
            PayloadTooLargeError: If more than 100 locations are provided.
        """
        if len(locations) > 100:
            raise ValueError("batch_search accepts at most 100 locations")
        response = self._client.post(
            "/batch/legal-location", json=locations
        )
        _raise_for_status(response)
        return [FeatureCollection.model_validate(fc) if fc is not None else None for fc in response.json()]

    def batch_reverse(
        self,
        coordinates: List[tuple[float, float]],
        *,
        unit: Optional[str] = None,
    ) -> List[Optional[FeatureCollection]]:
        """Find PLSS descriptions for multiple coordinate pairs in one request.

        Args:
            coordinates: List of ``(longitude, latitude)`` tuples (max 100).
            unit: Precision level — ``"Township"``, ``"First Division"``,
                ``"Second Division"``, or ``"all"``.

        Returns:
            A list of GeoJSON FeatureCollections (or None for no-match entries),
            one per coordinate pair.

        Raises:
            PayloadTooLargeError: If more than 100 coordinates are provided.
        """
        if len(coordinates) > 100:
            raise ValueError("batch_reverse accepts at most 100 coordinates")
        body: Dict[str, Any] = {"coordinates": [list(c) for c in coordinates]}
        if unit is not None:
            body["unit"] = unit
        response = self._client.post("/batch/coordinates", json=body)
        _raise_for_status(response)
        return [FeatureCollection.model_validate(fc) if fc is not None else None for fc in response.json()]


class AsyncTownshipAmerica:
    """Asynchronous client for the Township America API.

    Args:
        api_key: Your Township America API key.
        base_url: Override the default API base URL.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS to protect your API key in transit")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-API-Key": api_key, "User-Agent": "townshipamerica-python/0.1.0"},
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncTownshipAmerica":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # --- Search ---

    async def search(self, location: str) -> FeatureCollection:
        """Convert a PLSS legal land description to GPS coordinates.

        See :meth:`TownshipAmerica.search` for full documentation.
        """
        response = await self._client.get(
            "/search/legal-location", params={"location": location}
        )
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    async def reverse(
        self,
        longitude: float,
        latitude: float,
        *,
        unit: Optional[str] = None,
    ) -> FeatureCollection:
        """Find the PLSS legal land description at the given GPS coordinates.

        See :meth:`TownshipAmerica.reverse` for full documentation.
        """
        params: Dict[str, str] = {"location": f"{longitude},{latitude}"}
        if unit is not None:
            params["unit"] = unit
        response = await self._client.get("/search/coordinates", params=params)
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    # --- Autocomplete ---

    async def autocomplete(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        proximity: Optional[tuple[float, float]] = None,
    ) -> FeatureCollection:
        """Get autocomplete suggestions for a partial PLSS description.

        See :meth:`TownshipAmerica.autocomplete` for full documentation.
        """
        params: Dict[str, Union[str, int]] = {"location": query}
        if limit is not None:
            params["limit"] = limit
        if proximity is not None:
            params["proximity"] = f"{proximity[0]},{proximity[1]}"
        response = await self._client.get(
            "/autocomplete/legal-location", params=params
        )
        _raise_for_status(response)
        return FeatureCollection.model_validate(response.json())

    # --- Batch ---

    async def batch_search(
        self, locations: List[str]
    ) -> List[Optional[FeatureCollection]]:
        """Convert multiple PLSS descriptions to GPS coordinates in one request.

        See :meth:`TownshipAmerica.batch_search` for full documentation.
        """
        if len(locations) > 100:
            raise ValueError("batch_search accepts at most 100 locations")
        response = await self._client.post(
            "/batch/legal-location", json=locations
        )
        _raise_for_status(response)
        return [FeatureCollection.model_validate(fc) if fc is not None else None for fc in response.json()]

    async def batch_reverse(
        self,
        coordinates: List[tuple[float, float]],
        *,
        unit: Optional[str] = None,
    ) -> List[Optional[FeatureCollection]]:
        """Find PLSS descriptions for multiple coordinate pairs in one request.

        See :meth:`TownshipAmerica.batch_reverse` for full documentation.
        """
        if len(coordinates) > 100:
            raise ValueError("batch_reverse accepts at most 100 coordinates")
        body: Dict[str, Any] = {"coordinates": [list(c) for c in coordinates]}
        if unit is not None:
            body["unit"] = unit
        response = await self._client.post("/batch/coordinates", json=body)
        _raise_for_status(response)
        return [FeatureCollection.model_validate(fc) if fc is not None else None for fc in response.json()]
