"""Synchronous and asynchronous clients for the Township America API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

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
from .models import (
    EnergyReport,
    FeatureCollection,
    FederalLandReport,
    TexasProduction,
    TexasReport,
    TexasWell,
)

BASE_URL = "https://developer.townshipamerica.com"


def _raise_for_status(response: httpx.Response) -> None:
    """Translate HTTP error responses into typed exceptions."""
    if response.is_success:
        return

    code: Optional[str] = None
    try:
        body = response.json()
        error = body.get("error")
        if isinstance(error, dict):
            # Energy/Federal Land/Texas v1 error bodies: {"error": {"code", "message"}}
            message = error.get("message") or response.text
            code = error.get("code")
        else:
            message = error or body.get("message") or response.text
    except Exception:
        message = response.text

    status = response.status_code
    if status == 400:
        raise ValidationError(message, status_code=status, code=code)
    if status == 401:
        raise AuthenticationError(message, status_code=status, code=code)
    if status == 404:
        raise NotFoundError(message, status_code=status, code=code)
    if status == 413:
        raise PayloadTooLargeError(message, status_code=status, code=code)
    if status == 429:
        retry_after_raw = response.headers.get("retry-after")
        retry_after = float(retry_after_raw) if retry_after_raw else None
        raise RateLimitError(
            message, status_code=status, retry_after=retry_after, code=code
        )
    if status >= 500:
        raise ServerError(message, status_code=status, code=code)
    raise TownshipAmericaError(message, status_code=status, code=code)


def _report_params(
    legal_location: str, include: Optional[Sequence[str]]
) -> Dict[str, str]:
    """Build query params shared by the report endpoints."""
    params: Dict[str, str] = {"legal_location": legal_location}
    if include:
        params["include"] = ",".join(include)
    return params


def _texas_production_params(
    legal_location: Optional[str],
    county_fips: Optional[str],
    abstract_no: Optional[str],
    block_no: Optional[str],
) -> Dict[str, str]:
    """Build query params for /texas/production: legal_location OR registry keys."""
    if legal_location is not None:
        return {"legal_location": legal_location}
    if county_fips is not None and abstract_no is not None:
        params = {"county_fips": county_fips, "abstract_no": abstract_no}
        if block_no is not None:
            params["block_no"] = block_no
        return params
    raise ValueError(
        "texas_production requires either legal_location or county_fips + abstract_no"
    )


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
            headers={"X-API-Key": api_key, "User-Agent": "townshipamerica-python/2.0.0"},
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
        """Convert a PLSS or Texas TXSS legal land description to GPS coordinates.

        Args:
            location: A legal land description, e.g.
                ``"NW 25 24N 1E 6th Meridian"`` (PLSS) or
                ``"A-175 Reeves County"`` (Texas TXSS).

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
        """Find the legal land description at the given GPS coordinates (PLSS or TXSS).

        Args:
            longitude: Longitude (x) coordinate.
            latitude: Latitude (y) coordinate.
            unit: PLSS precision level — ``"Township"``, ``"First Division"``,
                ``"Second Division"``, or ``"all"``. Ignored for Texas TXSS results.

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
        """Get autocomplete suggestions for a partial PLSS or Texas TXSS description.

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
        """Convert multiple legal land descriptions to GPS coordinates in one request.

        Args:
            locations: List of PLSS or Texas TXSS descriptions (max 100). Mix freely.

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
        """Find legal land descriptions for multiple coordinate pairs in one request.

        Args:
            coordinates: List of ``(longitude, latitude)`` tuples (max 100).
            unit: PLSS precision level — ``"Township"``, ``"First Division"``,
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

    # --- Energy API ---

    def energy_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> EnergyReport:
        """Get the energy parcel report for a PLSS section.

        Covers state-regulator wells, operators, BLM federal leases, ONRR
        county royalties, orphaned wells, pipelines, FracFocus disclosures,
        and development constraints.

        Args:
            legal_location: A PLSS legal description, e.g.
                ``"NW 25 24N 1E 6th Meridian"``.
            include: Section projection — return only these sections (the
                omitted sections are never queried). Valid values:
                ``wells``, ``operators``, ``leases``, ``royalties``,
                ``orphaned_wells``, ``pipelines``, ``fracfocus``,
                ``constraints``, ``geometry``. ``geometry`` attaches the
                parcel boundary under ``parcel.geometry``.

        Returns:
            An EnergyReport. Sections degrade independently: a failed
            section lands in ``meta.unavailable`` instead of failing the
            report. Array sections are ``{total, returned, truncated,
            more, rows}`` envelopes.
        """
        response = self._client.get(
            "/energy/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return EnergyReport.model_validate(response.json())

    # --- Federal Land API ---

    def federal_land_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> FederalLandReport:
        """Get the federal-land parcel report for a PLSS tract.

        Covers surface management, BLM O&G and geothermal leases,
        rights-of-way, flood zones, mining claims, wetlands, firesheds,
        soils, crop history, orphaned wells, critical habitat, public
        access, wildfire risk, and elevation.

        Args:
            legal_location: A PLSS legal description, e.g.
                ``"NW 25 24N 1E 6th Meridian"``.
            include: Section projection — return only these sections (the
                pruned layers' spatial queries are skipped). Valid values:
                ``surface_management``, ``og_leases``, ``geothermal_leases``,
                ``rights_of_way``, ``flood_zones``, ``mining_claims``,
                ``wetlands``, ``fireshed``, ``soils``, ``crop_history``,
                ``orphaned_wells``, ``critical_habitat``, ``public_access``,
                ``wildfire_risk_communities``, ``elevation``, ``geometry``.

        Returns:
            A FederalLandReport. ``report_scope`` is
            ``"containing_section"`` when the tract is finer than the
            stored grid; a layer the state has no data for is listed in
            ``meta.unavailable`` with reason ``no_state_coverage``.
        """
        response = self._client.get(
            "/federal-land/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return FederalLandReport.model_validate(response.json())

    # --- Texas API ---

    def texas_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> TexasReport:
        """Get the Texas abstract report for a TXSS legal description.

        Covers GLO state leases and pooled units, PSF lands, state-agency
        lands, upland leases, RRC wells and T-4 pipelines, pending permits,
        coastal erosion, federal overlays, elevation, and RRC lease
        production.

        Args:
            legal_location: A Texas legal description, e.g.
                ``"A-175 Reeves County"``.
            include: Section projection — return only these sections (the
                pruned layers' spatial queries are skipped). Valid values:
                ``state_leases``, ``state_units``, ``psf_lands``,
                ``state_agency_lands``, ``upland_leases``, ``active_wells``,
                ``pipelines``, ``pending_permits``, ``coastal_erosion``,
                ``flood_zones``, ``wetlands``, ``fireshed``, ``soils``,
                ``orphaned_wells``, ``critical_habitat``,
                ``wildfire_risk_communities``, ``elevation``,
                ``production``, ``geometry``.

        Returns:
            A TexasReport. Array sections are ``{total, returned,
            truncated, more, rows}`` envelopes.
        """
        response = self._client.get(
            "/texas/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return TexasReport.model_validate(response.json())

    def texas_production(
        self,
        legal_location: Optional[str] = None,
        *,
        county_fips: Optional[str] = None,
        abstract_no: Optional[str] = None,
        block_no: Optional[str] = None,
    ) -> TexasProduction:
        """Get RRC lease production for a Texas abstract.

        Per-lease lifetime totals, trailing-12-month volumes, and the
        60-month monthly series. Key by a legal description OR the
        registry ids. Production is reported by RRC at the lease level —
        rows are the leases whose wells fall on the abstract, never
        sub-allocated to the tract.

        Args:
            legal_location: A Texas legal description, e.g.
                ``"A-175 Reeves County"``.
            county_fips: 5-digit county FIPS code, e.g. ``"48389"``
                (with ``abstract_no``, instead of ``legal_location``).
            abstract_no: Abstract number, e.g. ``"175"``.
            block_no: Block number, when the abstract is keyed by block.

        Returns:
            A TexasProduction rollup.

        Raises:
            ValueError: If neither ``legal_location`` nor
                ``county_fips`` + ``abstract_no`` is provided.
        """
        response = self._client.get(
            "/texas/production",
            params=_texas_production_params(
                legal_location, county_fips, abstract_no, block_no
            ),
        )
        _raise_for_status(response)
        return TexasProduction.model_validate(response.json())

    def texas_well(self, api: str) -> TexasWell:
        """Get per-well allocated production for a Texas well by API number.

        Summary scalars for every lease edge, the monthly series (when
        provisioned), and an Arps decline fit. Volumes are allocated
        estimates: RRC reports production by lease, never by well.

        Args:
            api: API-8 or API-14 number, e.g. ``"42-389-32345"`` or
                ``"42389323450000"``.

        Returns:
            A TexasWell with units, series, and decline analysis.
        """
        response = self._client.get(f"/texas/wells/{api}")
        _raise_for_status(response)
        return TexasWell.model_validate(response.json())


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
            headers={"X-API-Key": api_key, "User-Agent": "townshipamerica-python/2.0.0"},
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
        """Convert a PLSS or Texas TXSS legal land description to GPS coordinates.

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
        """Find the legal land description at the given GPS coordinates (PLSS or TXSS).

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
        """Get autocomplete suggestions for a partial PLSS or Texas TXSS description.

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
        """Convert multiple legal land descriptions to GPS coordinates in one request.

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
        """Find legal land descriptions for multiple coordinate pairs in one request.

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

    # --- Energy API ---

    async def energy_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> EnergyReport:
        """Get the energy parcel report for a PLSS section.

        See :meth:`TownshipAmerica.energy_report` for full documentation.
        """
        response = await self._client.get(
            "/energy/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return EnergyReport.model_validate(response.json())

    # --- Federal Land API ---

    async def federal_land_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> FederalLandReport:
        """Get the federal-land parcel report for a PLSS tract.

        See :meth:`TownshipAmerica.federal_land_report` for full documentation.
        """
        response = await self._client.get(
            "/federal-land/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return FederalLandReport.model_validate(response.json())

    # --- Texas API ---

    async def texas_report(
        self,
        legal_location: str,
        *,
        include: Optional[Sequence[str]] = None,
    ) -> TexasReport:
        """Get the Texas abstract report for a TXSS legal description.

        See :meth:`TownshipAmerica.texas_report` for full documentation.
        """
        response = await self._client.get(
            "/texas/report", params=_report_params(legal_location, include)
        )
        _raise_for_status(response)
        return TexasReport.model_validate(response.json())

    async def texas_production(
        self,
        legal_location: Optional[str] = None,
        *,
        county_fips: Optional[str] = None,
        abstract_no: Optional[str] = None,
        block_no: Optional[str] = None,
    ) -> TexasProduction:
        """Get RRC lease production for a Texas abstract.

        See :meth:`TownshipAmerica.texas_production` for full documentation.
        """
        response = await self._client.get(
            "/texas/production",
            params=_texas_production_params(
                legal_location, county_fips, abstract_no, block_no
            ),
        )
        _raise_for_status(response)
        return TexasProduction.model_validate(response.json())

    async def texas_well(self, api: str) -> TexasWell:
        """Get per-well allocated production for a Texas well by API number.

        See :meth:`TownshipAmerica.texas_well` for full documentation.
        """
        response = await self._client.get(f"/texas/wells/{api}")
        _raise_for_status(response)
        return TexasWell.model_validate(response.json())
