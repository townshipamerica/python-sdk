"""Pydantic models for Township America API request and response types."""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field


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


class MultiPolygon(BaseModel):
    """GeoJSON MultiPolygon geometry."""

    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: List[List[List[List[float]]]] = Field(
        ..., description="Array of polygon coordinate arrays"
    )


class FeatureProperties(BaseModel):
    """Properties attached to each GeoJSON Feature returned by the API."""

    shape: Optional[Literal["grid", "centroid"]] = None
    search_term: Optional[str] = None
    legal_location: Optional[str] = None
    alternate_legal_location: Optional[str] = None
    unit: Optional[str] = None
    survey_system: Optional[Literal["PLSS", "TXSS"]] = None
    county: Optional[str] = None
    state: Optional[str] = Field(None, description="US state name or abbreviation")
    abstract_no: Optional[str] = Field(None, description="Texas abstract number (TXSS)")
    block_no: Optional[str] = Field(None, description="Texas block number (TXSS)")
    survey_name: Optional[str] = Field(None, description="Texas survey name (TXSS)")
    acreage: Optional[float] = Field(None, description="Reported acreage when available (TXSS)")


class Feature(BaseModel):
    """GeoJSON Feature with Township America properties."""

    type: Literal["Feature"] = "Feature"
    geometry: Union[Point, Polygon, MultiPolygon] = Field(
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


# --- Report Models (Energy, Federal Land & Texas APIs) ---


RowT = TypeVar("RowT")


class _ReportSection(BaseModel):
    """Base for report sections: typed common fields, extra fields preserved."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class LatLng(_ReportSection):
    """A point as ``{lng, lat}`` (report payloads use this, not GeoJSON)."""

    lng: Optional[float] = None
    lat: Optional[float] = None


class EntityRef(_ReportSection):
    """A company reference wherever an operator/holder is named: ``{name}``."""

    name: Optional[str] = None


class SectionEnvelope(_ReportSection, Generic[RowT]):
    """Envelope every embedded array section of a report uses.

    ``total`` is the true count; ``truncated`` (and ``more``) flag that
    ``returned < total`` — silent truncation is never allowed.
    """

    total: int = 0
    returned: int = 0
    truncated: bool = False
    more: bool = False
    rows: List[RowT] = Field(default_factory=list)


class UnavailableSection(_ReportSection):
    """A section that could not be served, listed under ``meta.unavailable``."""

    section: Optional[str] = None
    reason: Optional[str] = None
    """``source_error``, ``timeout``, ``no_state_coverage``, or ``not_available``."""


class SectionSource(_ReportSection):
    """Upstream source of one report section (``as_of`` is None for now)."""

    name: Optional[str] = None
    as_of: Optional[str] = None


class ReportMeta(_ReportSection):
    """The ``meta`` block every report response carries."""

    unavailable: List[UnavailableSection] = Field(default_factory=list)
    sources: Optional[Dict[str, SectionSource]] = None
    note: Optional[str] = None
    """Present on Texas production/well responses (allocation caveat)."""


class ReportParcel(_ReportSection):
    """Parcel block shared by the reports: centroid + opt-in geometry."""

    centroid: Optional[LatLng] = None
    geometry: Optional[Union[Polygon, MultiPolygon]] = None
    """GeoJSON when requested with ``include=["geometry", ...]``, else None."""
    acreage: Optional[float] = None
    """Reported acreage (Texas abstracts only)."""


# --- Energy API models ---


class EnergyWellRow(_ReportSection):
    """One state-regulator well row (CO ECMC, ND DMR, OK OCC, WY WOGCC, NM OCD)."""

    api_number: Optional[str] = None
    source_state: Optional[str] = None
    operator: Optional[EntityRef] = None
    status: Optional[str] = None
    spud_date: Optional[str] = None
    formation: Optional[str] = None
    location: Optional[LatLng] = None
    distance_miles: Optional[float] = None


class EnergyOrphanedWellRow(_ReportSection):
    """One USGS documented orphaned well row (Energy API)."""

    well_id: Optional[str] = None
    state: Optional[str] = None
    operator: Optional[EntityRef] = None
    status: Optional[str] = None
    api_number: Optional[str] = None
    location: Optional[LatLng] = None
    distance_miles: Optional[float] = None


class EnergyLeaseRow(_ReportSection):
    """One BLM MLRS federal O&G lease row."""

    serial: Optional[str] = None
    status: Optional[str] = None
    holder: Optional[EntityRef] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    acreage: Optional[float] = None
    commodity: Optional[str] = None
    location: Optional[LatLng] = None
    """Representative point of the lease polygon."""


class EnergyOperatorRow(_ReportSection):
    """One distinct operator by well count near the parcel."""

    operator: Optional[EntityRef] = None
    well_count: Optional[int] = None


class EnergyRoyaltyItem(_ReportSection):
    """One commodity's county royalty rollup."""

    commodity: Optional[str] = None
    royalty_usd: Optional[float] = None


class EnergyRoyalties(_ReportSection):
    """ONRR county-level federal royalty rollup.

    County-wide, never parcel-precise — ``scope`` is always ``"county"``
    and labelled as such.
    """

    scope: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    years: Optional[int] = None
    total_usd: Optional[float] = None
    royalties: List[EnergyRoyaltyItem] = Field(default_factory=list)


class EnergyPipelineRow(_ReportSection):
    """One nearby HIFLD gas / NGL / crude trunk line row."""

    kind: Optional[str] = None
    kind_raw: Optional[str] = None
    operator: Optional[EntityRef] = None
    label: Optional[str] = None
    status: Optional[str] = None
    distance_miles: Optional[float] = None


class FracFocusRow(_ReportSection):
    """One FracFocus frac-job chemical disclosure row."""

    api_number: Optional[str] = None
    operator: Optional[EntityRef] = None
    well_name: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    disclosure_date: Optional[str] = None
    total_water_gal: Optional[float] = None
    total_proppant_lbs: Optional[float] = None
    location: Optional[LatLng] = None
    distance_miles: Optional[float] = None


class EnergySplitEstateSide(_ReportSection):
    """Surface or subsurface half of the split-estate check."""

    type: Optional[str] = None
    agency: Optional[str] = None
    coverage_pct: Optional[float] = None


class EnergySplitEstate(_ReportSection):
    """Split-estate check: surface vs subsurface ownership."""

    is_split_estate: Optional[bool] = None
    surface: Optional[EnergySplitEstateSide] = None
    subsurface: Optional[EnergySplitEstateSide] = None


class EnergySageGrouseHabitat(_ReportSection):
    """One BLM Sage-Grouse habitat overlay row."""

    designation: Optional[str] = None
    area_acres: Optional[float] = None
    overlap_acres: Optional[float] = None


class EnergySageGrouse(_ReportSection):
    """BLM Sage-Grouse habitat context."""

    in_habitat: Optional[bool] = None
    habitat_count: Optional[int] = None
    habitats: List[EnergySageGrouseHabitat] = Field(default_factory=list)


class EnergyRenewableSiting(_ReportSection):
    """NREL + BLM Solar + wind-turbine context for renewable siting."""

    nrel_score: Optional[float] = None
    blm_solar_zone: Optional[str] = None
    wind_turbines_within_2mi: Optional[int] = None
    notes: List[str] = Field(default_factory=list)


class EnergyConstraints(_ReportSection):
    """Development-constraint context. Each block degrades to None independently."""

    split_estate: Optional[EnergySplitEstate] = None
    sage_grouse: Optional[EnergySageGrouse] = None
    renewable_siting: Optional[EnergyRenewableSiting] = None


class EnergySummary(_ReportSection):
    """Per-section counts. A None count means that section was not fetched."""

    wells_in_section: Optional[int] = None
    wells_nearby: Optional[int] = None
    operators_nearby: Optional[int] = None
    federal_leases: Optional[int] = None
    orphaned_wells: Optional[int] = None
    pipelines_within_radius: Optional[int] = None
    fracfocus_disclosures: Optional[int] = None


class EnergyWellsNearby(SectionEnvelope[EnergyWellRow]):
    """Nearby-wells envelope with its search radius."""

    radius_mi: Optional[float] = None


class EnergyWells(_ReportSection):
    """Wells section: in-section rows + the nearby radius envelope."""

    in_section: Optional[SectionEnvelope[EnergyWellRow]] = None
    nearby: Optional[EnergyWellsNearby] = None


class EnergyOperatorsSection(SectionEnvelope[EnergyOperatorRow]):
    """Operators envelope with its search radius."""

    radius_mi: Optional[float] = None


class EnergyPipelinesSection(SectionEnvelope[EnergyPipelineRow]):
    """Pipelines envelope with its search radius."""

    radius_mi: Optional[float] = None


class FracFocusSection(SectionEnvelope[FracFocusRow]):
    """FracFocus envelope with its search radius."""

    radius_mi: Optional[float] = None


class EnergyReport(_ReportSection):
    """Per-parcel energy report, keyed at PLSS section grain.

    Sections degrade independently: a failed section lands in
    ``meta.unavailable`` instead of failing the report. Sections are
    ``None`` when omitted by an ``include=`` projection. Array sections
    are ``{total, returned, truncated, more, rows}`` envelopes.
    """

    legal_location: str
    resolved_legal_location: Optional[str] = None
    alternate_legal_location: Optional[str] = None
    unit: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    county: Optional[str] = None
    derived: Optional[bool] = None
    """Present only on tracts whose boundary was computed by subdivision."""
    parcel: Optional[ReportParcel] = None
    summary: Optional[EnergySummary] = None
    wells: Optional[EnergyWells] = None
    operators: Optional[EnergyOperatorsSection] = None
    leases: Optional[SectionEnvelope[EnergyLeaseRow]] = None
    royalties: Optional[EnergyRoyalties] = None
    orphaned_wells: Optional[SectionEnvelope[EnergyOrphanedWellRow]] = None
    pipelines: Optional[EnergyPipelinesSection] = None
    fracfocus: Optional[FracFocusSection] = None
    constraints: Optional[EnergyConstraints] = None
    meta: Optional[ReportMeta] = None


# --- Federal Land API models ---


class SurfaceManagementRow(_ReportSection):
    """One BLM Surface Management Agency row."""

    agency: Optional[str] = None
    admin_unit: Optional[str] = None


class FederalLeaseRow(_ReportSection):
    """One BLM MLRS lease row (O&G and geothermal share this shape)."""

    serial: Optional[str] = None
    status: Optional[str] = None
    lessee: Optional[str] = None
    expiration: Optional[str] = None
    location: Optional[LatLng] = None


class RightOfWayRow(_ReportSection):
    """One BLM MLRS right-of-way row."""

    serial: Optional[str] = None
    use_type: Optional[str] = None
    holder: Optional[str] = None
    status: Optional[str] = None
    location: Optional[LatLng] = None


class FloodZoneRow(_ReportSection):
    """One FEMA flood-zone row."""

    zone: Optional[str] = None
    subtype: Optional[str] = None
    sfha: Optional[bool] = None
    bfe: Optional[float] = None


class MiningClaimRow(_ReportSection):
    """One BLM MLRS mining-claim row."""

    case_id: Optional[str] = None
    case_type: Optional[str] = None
    claimant: Optional[str] = None
    status: Optional[str] = None


class WetlandRow(_ReportSection):
    """One USFWS wetland row."""

    wetland_type: Optional[str] = None
    attribute: Optional[str] = None
    acres: Optional[float] = None


class FireshedRow(_ReportSection):
    """One USFS fireshed row."""

    name: Optional[str] = None
    exposure_class: Optional[str] = None
    exposure_pct: Optional[float] = None
    homes_at_risk: Optional[float] = None


class SoilRow(_ReportSection):
    """One NRCS SSURGO soil map-unit row."""

    mukey: Optional[str] = None
    name: Optional[str] = None
    prime_farmland: Optional[str] = None
    hydric: Optional[str] = None


class OrphanedWellRow(_ReportSection):
    """One USGS documented orphaned well row (Federal Land / Texas APIs).

    ``operator`` is a plain string here; ``location`` is absent on
    Texas rows.
    """

    well_id: Optional[str] = None
    name: Optional[str] = None
    operator: Optional[str] = None
    status: Optional[str] = None
    api_number: Optional[str] = None
    location: Optional[LatLng] = None


class CriticalHabitatRow(_ReportSection):
    """One USFWS critical-habitat row."""

    common_name: Optional[str] = None
    scientific_name: Optional[str] = None
    listing_status: Optional[str] = None
    unit_name: Optional[str] = None
    feature_kind: Optional[str] = None


class PublicAccessRow(_ReportSection):
    """One BLM Public Land Access Data row."""

    plad_id: Optional[str] = None
    access_class: Optional[str] = None
    access_method: Optional[str] = None
    acres: Optional[float] = None
    admin_unit: Optional[str] = None


class WildfireRiskRow(_ReportSection):
    """One USFS Wildfire Risk to Communities block row."""

    block_geoid: Optional[str] = None
    risk_to_homes: Optional[float] = None
    burn_probability: Optional[float] = None
    exposure_type: Optional[str] = None
    housing_units: Optional[float] = None


class CropHistory(_ReportSection):
    """USDA NASS Cropland Data Layer summary (single object, never truncates)."""

    year: Optional[int] = None
    dominant_crop: Optional[str] = None
    dominant_crop_pct: Optional[float] = None
    distribution: Optional[Dict[str, Any]] = None


class Elevation(_ReportSection):
    """USGS 3DEP elevation summary (single object, never truncates)."""

    elev_min_m: Optional[float] = None
    elev_mean_m: Optional[float] = None
    elev_max_m: Optional[float] = None
    slope_mean_deg: Optional[float] = None
    aspect_dominant: Optional[str] = None


class FederalLandReport(_ReportSection):
    """Federal-land parcel report for one stored PLSS tract.

    ``report_scope`` is ``"parcel"`` when layer rows describe the resolved
    tract itself, or ``"containing_section"`` when the tract is finer than
    the stored grid (the section is named by ``report_section``). Sections
    are ``None`` when omitted by an ``include=`` projection.
    """

    legal_location: str
    resolved_legal_location: Optional[str] = None
    alternate_legal_location: Optional[str] = None
    unit: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    derived: Optional[bool] = None
    report_scope: Optional[str] = None
    report_section: Optional[str] = None
    parcel: Optional[ReportParcel] = None
    surface_management: Optional[SectionEnvelope[SurfaceManagementRow]] = None
    og_leases: Optional[SectionEnvelope[FederalLeaseRow]] = None
    geothermal_leases: Optional[SectionEnvelope[FederalLeaseRow]] = None
    rights_of_way: Optional[SectionEnvelope[RightOfWayRow]] = None
    flood_zones: Optional[SectionEnvelope[FloodZoneRow]] = None
    mining_claims: Optional[SectionEnvelope[MiningClaimRow]] = None
    wetlands: Optional[SectionEnvelope[WetlandRow]] = None
    fireshed: Optional[SectionEnvelope[FireshedRow]] = None
    soils: Optional[SectionEnvelope[SoilRow]] = None
    crop_history: Optional[CropHistory] = None
    orphaned_wells: Optional[SectionEnvelope[OrphanedWellRow]] = None
    critical_habitat: Optional[SectionEnvelope[CriticalHabitatRow]] = None
    public_access: Optional[SectionEnvelope[PublicAccessRow]] = None
    wildfire_risk_communities: Optional[SectionEnvelope[WildfireRiskRow]] = None
    elevation: Optional[Elevation] = None
    meta: Optional[ReportMeta] = None


# --- Texas API models ---


class TexasStateLeaseRow(_ReportSection):
    """One Texas GLO active O&G state lease row."""

    lease_no: Optional[str] = None
    lessee: Optional[str] = None
    status: Optional[str] = None
    mineral_type: Optional[str] = None
    expiration: Optional[str] = None
    royalty_rate: Optional[float] = None


class TexasStateUnitRow(_ReportSection):
    """One Texas GLO pooled-unit row."""

    lease_no: Optional[str] = None
    unit_name: Optional[str] = None
    lease_status: Optional[str] = None
    lease_type: Optional[str] = None


class TexasPsfLandRow(_ReportSection):
    """One Texas GLO Permanent School Fund land row."""

    control_number: Optional[str] = None
    survey: Optional[str] = None
    deed_acres: Optional[float] = None


class TexasStateAgencyLandRow(_ReportSection):
    """One Texas state-agency land row."""

    control_number: Optional[str] = None
    land_name: Optional[str] = None
    land_type: Optional[str] = None


class TexasUplandLeaseRow(_ReportSection):
    """One Texas GLO upland surface lease row."""

    lease_number: Optional[str] = None
    lease_status: Optional[str] = None
    activity: Optional[str] = None
    primary_lessee: Optional[str] = None


class TexasActiveWellRow(_ReportSection):
    """One Texas RRC well row (surface locations)."""

    api_number: Optional[str] = None
    operator: Optional[str] = None
    lease_name: Optional[str] = None
    well_number: Optional[str] = None
    status: Optional[str] = None
    status_raw: Optional[str] = None
    formation: Optional[str] = None
    field: Optional[str] = None
    location: Optional[LatLng] = None


class TexasPipelineRow(_ReportSection):
    """One Texas RRC T-4 pipeline row."""

    pipeline_id: Optional[str] = None
    operator_no: Optional[str] = None
    commodity: Optional[str] = None
    diameter_in: Optional[float] = None
    status: Optional[str] = None
    overlap_point: Optional[LatLng] = None
    """Nearest point of the line to the parcel."""


class TexasPendingPermitRow(_ReportSection):
    """One Texas RRC pending drilling permit row."""

    permit_no: Optional[str] = None
    operator_name: Optional[str] = None


class TexasCoastalErosionRow(_ReportSection):
    """One Texas GLO critical erosion area row."""

    site: Optional[str] = None
    rate_ep_ft_yr: Optional[float] = None
    rate_lr_ft_yr: Optional[float] = None
    r_squared: Optional[float] = None


class TexasMonthlyVolume(_ReportSection):
    """One month of a lease's 60-month production sparkline."""

    ym: Optional[str] = None
    oil_bbl: Optional[float] = None
    gas_mcf: Optional[float] = None
    water_bbl: Optional[float] = None


class TexasProductionLease(_ReportSection):
    """One RRC lease production rollup.

    Production is reported by RRC at the LEASE level (not per tract): the
    rows are the leases whose wells fall on the abstract with their full
    lifetime totals.
    """

    operator: Optional[EntityRef] = None
    district_no: Optional[str] = None
    lease_no: Optional[str] = None
    oil_gas_code: Optional[str] = None
    cum_oil_bbl: Optional[float] = None
    cum_gas_mcf: Optional[float] = None
    cum_boe: Optional[float] = None
    ttm_oil_bbl: Optional[float] = None
    ttm_gas_mcf: Optional[float] = None
    first_month: Optional[str] = None
    last_month: Optional[str] = None
    peak_month: Optional[str] = None
    months_producing: Optional[int] = None
    monthly: List[TexasMonthlyVolume] = Field(default_factory=list)


class TexasAbstractRef(_ReportSection):
    """The abstract the production rollup describes."""

    county_fips: Optional[str] = None
    abstract_no: Optional[str] = None


class TexasProductionSummary(_ReportSection):
    """Abstract-level production summary across the returned leases."""

    producing_lease_count: Optional[int] = None
    total_cum_boe: Optional[float] = None
    total_cum_oil_bbl: Optional[float] = None
    total_cum_gas_mcf: Optional[float] = None
    ttm_boe: Optional[float] = None
    first_month: Optional[str] = None
    last_month: Optional[str] = None


class TexasProductionBlock(_ReportSection):
    """The production block embedded in the Texas report."""

    abstract: Optional[TexasAbstractRef] = None
    summary: Optional[TexasProductionSummary] = None
    leases: Optional[SectionEnvelope[TexasProductionLease]] = None


class TexasProduction(TexasProductionBlock):
    """``GET /texas/production`` response: identity + the production rollup."""

    county_fips: Optional[str] = None
    county: Optional[str] = None
    abstract_no: Optional[str] = None
    block_no: Optional[str] = None
    meta: Optional[ReportMeta] = None


class TexasReport(_ReportSection):
    """Full Texas abstract report, keyed on the Abstract/Block/Survey grid.

    Sections are ``None`` when omitted by an ``include=`` projection.
    Array sections are ``{total, returned, truncated, more, rows}``
    envelopes.
    """

    legal_location: str
    resolved_legal_location: Optional[str] = None
    alternate_legal_location: Optional[str] = None
    county_fips: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    abstract_no: Optional[str] = None
    block_no: Optional[str] = None
    survey_name: Optional[str] = None
    parcel: Optional[ReportParcel] = None
    state_leases: Optional[SectionEnvelope[TexasStateLeaseRow]] = None
    state_units: Optional[SectionEnvelope[TexasStateUnitRow]] = None
    psf_lands: Optional[SectionEnvelope[TexasPsfLandRow]] = None
    state_agency_lands: Optional[SectionEnvelope[TexasStateAgencyLandRow]] = None
    upland_leases: Optional[SectionEnvelope[TexasUplandLeaseRow]] = None
    active_wells: Optional[SectionEnvelope[TexasActiveWellRow]] = None
    pipelines: Optional[SectionEnvelope[TexasPipelineRow]] = None
    pending_permits: Optional[SectionEnvelope[TexasPendingPermitRow]] = None
    coastal_erosion: Optional[SectionEnvelope[TexasCoastalErosionRow]] = None
    flood_zones: Optional[SectionEnvelope[FloodZoneRow]] = None
    wetlands: Optional[SectionEnvelope[WetlandRow]] = None
    fireshed: Optional[SectionEnvelope[FireshedRow]] = None
    soils: Optional[SectionEnvelope[SoilRow]] = None
    orphaned_wells: Optional[SectionEnvelope[OrphanedWellRow]] = None
    critical_habitat: Optional[SectionEnvelope[CriticalHabitatRow]] = None
    wildfire_risk_communities: Optional[SectionEnvelope[WildfireRiskRow]] = None
    elevation: Optional[Elevation] = None
    production: Optional[TexasProductionBlock] = None
    meta: Optional[ReportMeta] = None


class TexasWellLocation(_ReportSection):
    """The subject well's own location and formation context."""

    api_number: Optional[str] = None
    location: Optional[LatLng] = None
    operator: Optional[EntityRef] = None
    lease_name: Optional[str] = None
    well_number: Optional[str] = None
    field: Optional[str] = None
    formation: Optional[str] = None
    status: Optional[str] = None
    spud_date: Optional[str] = None
    district: Optional[str] = None
    county_fips: Optional[str] = None
    abstract_no: Optional[str] = None


class TexasWellUnit(_ReportSection):
    """One reporting unit (RRC lease edge) of a well.

    Volumes are ALLOCATED ESTIMATES — RRC reports production by lease,
    never by well. ``denominator_basis`` records whether the allocation
    used the completion-date denominator (``"time_varying"``) or fell back
    to a static split (``"static"``).
    """

    district_no: Optional[str] = None
    lease_no: Optional[str] = None
    oil_gas_code: Optional[str] = None
    operator: Optional[EntityRef] = None
    peak_oil_bbl: Optional[float] = None
    cum_boe: Optional[float] = None
    well_count: Optional[int] = None
    denominator_basis: Optional[str] = None


class TexasWellSeriesPoint(_ReportSection):
    """One month of a well's allocated production series."""

    ym: Optional[str] = None
    oil_bbl: Optional[float] = None
    gas_mcf: Optional[float] = None


class TexasDeclineFit(_ReportSection):
    """The fitted Arps decline parameters."""

    qi: Optional[float] = None
    di: Optional[float] = None
    b: Optional[float] = None
    r2: Optional[float] = None
    points: Optional[int] = None


class TexasDecline(_ReportSection):
    """Arps decline fit on the well's post-peak oil series.

    Withheld (``available=False``) when the fit quality is below
    threshold — a confident-looking forecast off a noisy allocated series
    is worse than none. ``reason`` is ``insufficient_points``,
    ``no_valid_fit``, or ``fit_quality_below_threshold``.
    """

    available: bool = False
    reason: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    value: Optional[TexasDeclineFit] = None


class TexasDeclineCurvePoint(_ReportSection):
    """One point of the fitted decline curve, on the same months as the series."""

    ym: Optional[str] = None
    q: Optional[float] = None


class TexasWellSeriesUnit(_ReportSection):
    """The reporting unit a well's monthly series is scoped to."""

    district_no: Optional[str] = None
    lease_no: Optional[str] = None
    oil_gas_code: Optional[str] = None


class TexasWell(_ReportSection):
    """``GET /texas/wells/{api}`` response.

    Per-well units, the monthly allocated series (when provisioned), and
    an Arps decline fit. Volumes are allocated estimates — RRC reports
    production by lease, never by well.
    """

    api8: Optional[str] = None
    location: Optional[TexasWellLocation] = None
    units: List[TexasWellUnit] = Field(default_factory=list)
    series: List[TexasWellSeriesPoint] = Field(default_factory=list)
    series_unit: Optional[TexasWellSeriesUnit] = None
    """The series is scoped to the well's PRIMARY unit."""
    series_covers_all_units: Optional[bool] = None
    decline: Optional[TexasDecline] = None
    decline_curve: Optional[List[TexasDeclineCurvePoint]] = None
    meta: Optional[ReportMeta] = None
