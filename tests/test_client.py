"""Tests for the Township America Python SDK client."""

import httpx
import pytest
import respx

from townshipamerica import (
    AsyncTownshipAmerica,
    AuthenticationError,
    EnergyReport,
    FeatureCollection,
    FederalLandReport,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
    TexasProduction,
    TexasReport,
    TexasWell,
    TownshipAmerica,
    ValidationError,
)

SEARCH_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-104.013432, 41.077909],
                        [-104.013424, 41.074288],
                        [-104.025062, 41.081578],
                        [-104.013432, 41.077909],
                    ]
                ],
            },
            "properties": {
                "shape": "grid",
                "search_term": "NW 25 24N 1E 6th Meridian",
                "legal_location": "NW 25 24N 1E 6th Meridian",
                "alternate_legal_location": "NW 25 24N 1E Weld County Colorado",
                "unit": "First Division",
                "survey_system": "PLSS",
                "county": "Weld",
                "state": "Colorado",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-104.01924, 41.077932],
            },
            "properties": {
                "shape": "centroid",
                "search_term": "NW 25 24N 1E 6th Meridian",
                "legal_location": "NW 25 24N 1E 6th Meridian",
                "alternate_legal_location": "NW 25 24N 1E Weld County Colorado",
                "unit": "First Division",
                "survey_system": "PLSS",
                "county": "Weld",
                "state": "Colorado",
            },
        },
    ],
}

AUTOCOMPLETE_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-104.01924, 41.077932],
            },
            "properties": {
                "shape": "centroid",
                "search_term": "NW 25",
                "legal_location": "NW 25 24N 1E 6th Meridian",
                "unit": "First Division",
                "survey_system": "PLSS",
                "state": "Colorado",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-104.12345, 41.06789],
            },
            "properties": {
                "shape": "centroid",
                "search_term": "NW 25",
                "legal_location": "NW 25 24N 1W 6th Meridian",
                "unit": "First Division",
                "survey_system": "PLSS",
                "state": "Colorado",
            },
        },
    ],
}

BASE = "https://developer.townshipamerica.com"

TX_SEARCH_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [-103.5, 31.2],
                            [-103.4, 31.2],
                            [-103.4, 31.3],
                            [-103.5, 31.3],
                            [-103.5, 31.2],
                        ]
                    ]
                ],
            },
            "properties": {
                "shape": "grid",
                "search_term": "A-175 Reeves County",
                "legal_location": "Abstract 175 Reeves County Texas",
                "alternate_legal_location": "A-175 Reeves Co Texas",
                "unit": None,
                "survey_system": "TXSS",
                "county": "Reeves",
                "state": "TX",
                "abstract_no": "175",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-103.45, 31.25],
            },
            "properties": {
                "shape": "centroid",
                "search_term": "A-175 Reeves County",
                "legal_location": "Abstract 175 Reeves County Texas",
                "unit": None,
                "survey_system": "TXSS",
                "county": "Reeves",
                "state": "TX",
                "abstract_no": "175",
            },
        },
    ],
}


class TestSyncClient:
    """Tests for the synchronous TownshipAmerica client."""

    @respx.mock
    def test_search(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            result = ta.search("NW 25 24N 1E 6th Meridian")

        assert isinstance(result, FeatureCollection)
        assert result.centroid is not None
        assert result.centroid.geometry.latitude == pytest.approx(41.077932)
        assert result.centroid.geometry.longitude == pytest.approx(-104.01924)
        assert result.grid is not None
        assert result.centroid.properties.state == "Colorado"

    @respx.mock
    def test_search_txss_multipolygon(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(200, json=TX_SEARCH_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            result = ta.search("A-175 Reeves County")

        assert result.centroid.properties.survey_system == "TXSS"
        assert result.centroid.properties.state == "TX"
        assert result.centroid.properties.abstract_no == "175"
        assert result.grid is not None
        assert result.grid.geometry.type == "MultiPolygon"

    @respx.mock
    def test_autocomplete_txss(self):
        tx_autocomplete = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-103.45, 31.25]},
                    "properties": {
                        "shape": "centroid",
                        "search_term": "A-175",
                        "legal_location": "Abstract 175 Reeves County Texas",
                        "survey_system": "TXSS",
                        "state": "TX",
                    },
                }
            ],
        }
        respx.get(f"{BASE}/autocomplete/legal-location").mock(
            return_value=httpx.Response(200, json=tx_autocomplete)
        )
        with TownshipAmerica("test-key") as ta:
            result = ta.autocomplete("A-175", limit=3)

        assert result.features[0].properties.survey_system == "TXSS"

    @respx.mock
    def test_batch_search_mixed_plss_txss(self):
        batch_response = [SEARCH_RESPONSE, TX_SEARCH_RESPONSE, None]
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        with TownshipAmerica("test-key") as ta:
            results = ta.batch_search(
                ["NW 25 24N 1E 6th Meridian", "A-175 Reeves County", "invalid"]
            )

        assert results[0].centroid.properties.survey_system == "PLSS"
        assert results[1].centroid.properties.survey_system == "TXSS"
        assert results[2] is None

    @respx.mock
    def test_reverse(self):
        respx.get(f"{BASE}/search/coordinates").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            result = ta.reverse(-104.01924, 41.077932, unit="First Division")

        assert isinstance(result, FeatureCollection)
        assert len(result.features) == 2

    @respx.mock
    def test_autocomplete(self):
        respx.get(f"{BASE}/autocomplete/legal-location").mock(
            return_value=httpx.Response(200, json=AUTOCOMPLETE_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            result = ta.autocomplete("NW 25", limit=5)

        assert isinstance(result, FeatureCollection)
        assert len(result.features) == 2
        assert result.features[0].properties.legal_location == "NW 25 24N 1E 6th Meridian"

    @respx.mock
    def test_batch_search(self):
        batch_response = [SEARCH_RESPONSE, SEARCH_RESPONSE]
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        with TownshipAmerica("test-key") as ta:
            results = ta.batch_search(
                ["NW 25 24N 1E 6th Meridian", "NE 12 4N 5E Indian Meridian"]
            )

        assert len(results) == 2
        assert all(isinstance(r, FeatureCollection) for r in results)

    @respx.mock
    def test_batch_search_with_null(self):
        batch_response = [SEARCH_RESPONSE, None]
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        with TownshipAmerica("test-key") as ta:
            results = ta.batch_search(
                ["NW 25 24N 1E 6th Meridian", "invalid location"]
            )

        assert len(results) == 2
        assert isinstance(results[0], FeatureCollection)
        assert results[1] is None

    @respx.mock
    def test_batch_reverse(self):
        batch_response = [SEARCH_RESPONSE, SEARCH_RESPONSE]
        respx.post(f"{BASE}/batch/coordinates").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        with TownshipAmerica("test-key") as ta:
            results = ta.batch_reverse(
                [(-104.01924, 41.077932), (-104.648933, 41.454928)]
            )

        assert len(results) == 2

    @respx.mock
    def test_auth_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(401, json={"message": "Invalid API key"})
        )
        with TownshipAmerica("bad-key") as ta:
            with pytest.raises(AuthenticationError) as exc_info:
                ta.search("NW 25 24N 1E 6th Meridian")
        assert exc_info.value.status_code == 401

    @respx.mock
    def test_not_found_error(self):
        respx.get(f"{BASE}/search/coordinates").mock(
            return_value=httpx.Response(404, json={"message": "No results found"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(NotFoundError):
                ta.reverse(0.0, 0.0)

    @respx.mock
    def test_validation_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(400, json={"message": "Invalid location"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValidationError):
                ta.search("invalid")

    @respx.mock
    def test_rate_limit_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(429, json={"message": "Rate limit exceeded"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(RateLimitError):
                ta.search("NW 25 24N 1E 6th Meridian")

    @respx.mock
    def test_server_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(502, json={"message": "Bad Gateway"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ServerError) as exc_info:
                ta.search("NW 25 24N 1E 6th Meridian")
        assert exc_info.value.status_code == 502

    @respx.mock
    def test_payload_too_large_error(self):
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(413, json={"message": "Payload too large"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(PayloadTooLargeError):
                ta.batch_search(["loc"] * 50)

    def test_batch_search_client_validation(self):
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValueError, match="at most 100"):
                ta.batch_search(["loc"] * 101)

    def test_batch_reverse_client_validation(self):
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValueError, match="at most 100"):
                ta.batch_reverse([(0.0, 0.0)] * 101)

    @respx.mock
    def test_rate_limit_with_retry_after(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(
                429,
                json={"message": "Rate limit exceeded"},
                headers={"Retry-After": "30"},
            )
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(RateLimitError) as exc_info:
                ta.search("NW 25 24N 1E 6th Meridian")
        assert exc_info.value.retry_after == 30.0

    def test_https_enforcement(self):
        with pytest.raises(ValueError, match="HTTPS"):
            TownshipAmerica("key", base_url="http://example.com")


class TestAsyncClient:
    """Tests for the async AsyncTownshipAmerica client."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_search(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            result = await ta.search("NW 25 24N 1E 6th Meridian")

        assert isinstance(result, FeatureCollection)
        assert result.centroid is not None

    @respx.mock
    @pytest.mark.asyncio
    async def test_batch_search(self):
        batch_response = [SEARCH_RESPONSE, SEARCH_RESPONSE]
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            results = await ta.batch_search(
                ["NW 25 24N 1E 6th Meridian", "NE 12 4N 5E Indian Meridian"]
            )

        assert len(results) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_reverse(self):
        respx.get(f"{BASE}/search/coordinates").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            result = await ta.reverse(-104.01924, 41.077932, unit="First Division")
        assert isinstance(result, FeatureCollection)
        assert len(result.features) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_autocomplete(self):
        respx.get(f"{BASE}/autocomplete/legal-location").mock(
            return_value=httpx.Response(200, json=AUTOCOMPLETE_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            result = await ta.autocomplete("NW 25", limit=5)
        assert isinstance(result, FeatureCollection)
        assert len(result.features) == 2
        assert result.features[0].properties.legal_location == "NW 25 24N 1E 6th Meridian"

    @respx.mock
    @pytest.mark.asyncio
    async def test_batch_reverse(self):
        batch_response = [SEARCH_RESPONSE, SEARCH_RESPONSE]
        respx.post(f"{BASE}/batch/coordinates").mock(
            return_value=httpx.Response(200, json=batch_response)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            results = await ta.batch_reverse(
                [(-104.01924, 41.077932), (-104.648933, 41.454928)]
            )
        assert len(results) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(401, json={"message": "Invalid API key"})
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            with pytest.raises(AuthenticationError) as exc_info:
                await ta.search("NW 25 24N 1E 6th Meridian")
        assert exc_info.value.status_code == 401

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(429, json={"message": "Rate limit exceeded"})
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            with pytest.raises(RateLimitError):
                await ta.search("NW 25 24N 1E 6th Meridian")


EMPTY_SECTION = {"total": 0, "returned": 0, "truncated": False, "more": False, "rows": []}

ENERGY_REPORT_RESPONSE = {
    "legal_location": "25 24N 1E 6th Meridian",
    "resolved_legal_location": "25 24N 1E 6th Meridian",
    "alternate_legal_location": "25 T24N R1E 6th PM",
    "unit": "First Division",
    "state": "Colorado",
    "state_code": "CO",
    "county": "Weld",
    "parcel": {"centroid": {"lng": -104.01924, "lat": 41.077932}, "geometry": None},
    "summary": {
        "wells_in_section": 1,
        "wells_nearby": 3,
        "operators_nearby": 1,
        "federal_leases": 1,
        "orphaned_wells": 0,
        "pipelines_within_radius": 1,
        "fracfocus_disclosures": 0,
    },
    "wells": {
        "in_section": {
            "total": 1,
            "returned": 1,
            "truncated": False,
            "more": False,
            "rows": [
                {
                    "api_number": "05-123-45678",
                    "source_state": "CO",
                    "operator": {"name": "EXAMPLE ENERGY LLC"},
                    "status": "PR",
                    "spud_date": "2019-06-01",
                    "formation": "NIOBRARA",
                    "location": {"lng": -104.02, "lat": 41.078},
                    "distance_miles": 0.12,
                }
            ],
        },
        "nearby": {
            "radius_mi": 1,
            "total": 3,
            "returned": 3,
            "truncated": False,
            "more": False,
            "rows": [],
        },
    },
    "operators": {
        "radius_mi": 1,
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [{"operator": {"name": "EXAMPLE ENERGY LLC"}, "well_count": 3}],
    },
    "leases": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "serial": "COC123456",
                "status": "AUTHORIZED",
                "holder": {"name": "EXAMPLE ENERGY LLC"},
                "effective_date": "2015-05-01",
                "expiration_date": "2025-04-30",
                "acreage": 640,
                "commodity": "Oil & Gas",
                "location": {"lng": -104.02, "lat": 41.077},
            }
        ],
    },
    "royalties": {
        "scope": "county",
        "state": "Colorado",
        "county": "Weld",
        "years": 10,
        "total_usd": 1234567.89,
        "royalties": [{"commodity": "Oil", "royalty_usd": 1234567.89}],
    },
    "orphaned_wells": EMPTY_SECTION,
    "pipelines": {
        "radius_mi": 5,
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "kind": "gas",
                "kind_raw": "Gas",
                "operator": {"name": "EXAMPLE MIDSTREAM"},
                "label": "Interstate",
                "status": "Active",
                "distance_miles": 2.31,
            }
        ],
    },
    "fracfocus": {"radius_mi": 1, **EMPTY_SECTION},
    "constraints": {
        "split_estate": {
            "is_split_estate": True,
            "surface": {"type": "private", "agency": None, "coverage_pct": 0.01},
            "subsurface": {"type": "federal", "agency": "BLM", "coverage_pct": 0.97},
        },
        "sage_grouse": {"in_habitat": False, "habitat_count": 0, "habitats": []},
        "renewable_siting": {
            "nrel_score": 62.5,
            "blm_solar_zone": None,
            "wind_turbines_within_2mi": 3,
            "notes": ["3 wind turbines within 2 miles"],
        },
    },
    "meta": {
        "unavailable": [],
        "sources": {
            "wells": {
                "name": "State regulators (CO ECMC, ND DMR, OK OCC, WY WOGCC, NM OCD)",
                "as_of": None,
            }
        },
    },
}

FEDERAL_LAND_REPORT_RESPONSE = {
    "legal_location": "NW 25 24N 1E 6th Meridian",
    "resolved_legal_location": "NW 25 24N 1E 6th Meridian",
    "alternate_legal_location": "NW 25 T24N R1E 6th PM",
    "unit": "Second Division",
    "state": "Colorado",
    "county": "Weld",
    "report_scope": "parcel",
    "parcel": {"centroid": {"lng": -104.01924, "lat": 41.077932}, "geometry": None},
    "surface_management": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [{"agency": "BLM", "admin_unit": "Royal Gorge Field Office"}],
    },
    "og_leases": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "serial": "COC123456",
                "status": "AUTHORIZED",
                "lessee": "EXAMPLE ENERGY LLC",
                "expiration": "2025-04-30",
                "location": {"lng": -104.02, "lat": 41.077},
            }
        ],
    },
    "geothermal_leases": EMPTY_SECTION,
    "rights_of_way": EMPTY_SECTION,
    "flood_zones": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [{"zone": "AE", "subtype": "FLOODWAY", "sfha": True, "bfe": 1520}],
    },
    "mining_claims": EMPTY_SECTION,
    "wetlands": EMPTY_SECTION,
    "fireshed": EMPTY_SECTION,
    "soils": EMPTY_SECTION,
    "crop_history": {
        "year": 2024,
        "dominant_crop": "Winter Wheat",
        "dominant_crop_pct": 61.2,
        "distribution": {"Winter Wheat": 61.2, "Fallow": 38.8},
    },
    "orphaned_wells": EMPTY_SECTION,
    "critical_habitat": EMPTY_SECTION,
    "public_access": EMPTY_SECTION,
    "wildfire_risk_communities": EMPTY_SECTION,
    "elevation": {
        "elev_min_m": 1502.1,
        "elev_mean_m": 1520.4,
        "elev_max_m": 1541.7,
        "slope_mean_deg": 1.8,
        "aspect_dominant": "E",
    },
    "meta": {
        "unavailable": [{"section": "fireshed", "reason": "no_state_coverage"}],
        "sources": {
            "surface_management": {
                "name": "BLM Surface Management Agency (SMA)",
                "as_of": None,
            }
        },
    },
}

TEXAS_PRODUCTION_BLOCK = {
    "abstract": {"county_fips": "48389", "abstract_no": "175"},
    "summary": {
        "producing_lease_count": 1,
        "total_cum_boe": 125000,
        "total_cum_oil_bbl": 100000,
        "total_cum_gas_mcf": 150000,
        "ttm_boe": 9000,
        "first_month": "2018-03",
        "last_month": "2026-05",
    },
    "leases": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "operator": {"name": "EXAMPLE OPERATING CO"},
                "district_no": "08",
                "lease_no": "12345",
                "oil_gas_code": "O",
                "cum_oil_bbl": 100000,
                "cum_gas_mcf": 150000,
                "cum_boe": 125000,
                "ttm_oil_bbl": 8000,
                "ttm_gas_mcf": 6000,
                "first_month": "2018-03",
                "last_month": "2026-05",
                "peak_month": "2018-09",
                "months_producing": 96,
                "monthly": [
                    {"ym": "2026-05", "oil_bbl": 900, "gas_mcf": 700, "water_bbl": 1200}
                ],
            }
        ],
    },
}

TEXAS_REPORT_RESPONSE = {
    "legal_location": "A-175 Reeves County",
    "resolved_legal_location": "Abstract 175 Reeves County Texas",
    "alternate_legal_location": "A-175 Reeves Co Texas",
    "county_fips": "48389",
    "county": "Reeves",
    "state": "TX",
    "abstract_no": "175",
    "block_no": None,
    "survey_name": "H&GN RR CO",
    "parcel": {
        "acreage": 640,
        "centroid": {"lng": -103.45, "lat": 31.25},
        "geometry": None,
    },
    "state_leases": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "lease_no": "MF123456",
                "lessee": "EXAMPLE OPERATING CO",
                "status": "Active",
                "mineral_type": "Oil & Gas",
                "expiration": "2027-01-31",
                "royalty_rate": 0.25,
            }
        ],
    },
    "state_units": EMPTY_SECTION,
    "psf_lands": EMPTY_SECTION,
    "state_agency_lands": EMPTY_SECTION,
    "upland_leases": EMPTY_SECTION,
    "active_wells": {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "more": False,
        "rows": [
            {
                "api_number": "42-389-32345",
                "operator": "EXAMPLE OPERATING CO",
                "lease_name": "EXAMPLE UNIT",
                "well_number": "1H",
                "status": "Producing",
                "status_raw": "P",
                "formation": "WOLFCAMP",
                "field": "PHANTOM (WOLFCAMP)",
                "location": {"lng": -103.45, "lat": 31.25},
            }
        ],
    },
    "pipelines": EMPTY_SECTION,
    "pending_permits": EMPTY_SECTION,
    "coastal_erosion": EMPTY_SECTION,
    "flood_zones": EMPTY_SECTION,
    "wetlands": EMPTY_SECTION,
    "fireshed": EMPTY_SECTION,
    "soils": EMPTY_SECTION,
    "orphaned_wells": EMPTY_SECTION,
    "critical_habitat": EMPTY_SECTION,
    "wildfire_risk_communities": EMPTY_SECTION,
    "elevation": None,
    "production": TEXAS_PRODUCTION_BLOCK,
    "meta": {
        "unavailable": [],
        "sources": {
            "state_leases": {"name": "Texas GLO Active O&G Leases", "as_of": None}
        },
    },
}

TEXAS_PRODUCTION_RESPONSE = {
    "county_fips": "48389",
    "county": "Reeves",
    "abstract_no": "175",
    "block_no": None,
    **TEXAS_PRODUCTION_BLOCK,
    "meta": {"unavailable": []},
}

TEXAS_WELL_RESPONSE = {
    "api8": "42389323",
    "location": {
        "api_number": "42-389-32345",
        "location": {"lng": -103.45, "lat": 31.25},
        "operator": {"name": "EXAMPLE OPERATING CO"},
        "lease_name": "EXAMPLE UNIT",
        "well_number": "1H",
        "field": "PHANTOM (WOLFCAMP)",
        "formation": "WOLFCAMP",
        "status": "Producing",
        "spud_date": "2018-01-15",
        "district": "08",
        "county_fips": "48389",
        "abstract_no": "175",
    },
    "units": [
        {
            "district_no": "08",
            "lease_no": "12345",
            "oil_gas_code": "O",
            "operator": {"name": "EXAMPLE OPERATING CO"},
            "peak_oil_bbl": 15000,
            "cum_boe": 125000,
            "well_count": 1,
            "denominator_basis": "time_varying",
        }
    ],
    "series": [
        {"ym": "2018-03", "oil_bbl": 12000, "gas_mcf": 9000},
        {"ym": "2018-04", "oil_bbl": 15000, "gas_mcf": 11000},
    ],
    "series_unit": {"district_no": "08", "lease_no": "12345", "oil_gas_code": "O"},
    "series_covers_all_units": True,
    "decline": {
        "available": True,
        "value": {"qi": 15000, "di": 0.08, "b": 0.5, "r2": 0.91, "points": 24},
    },
    "decline_curve": [{"ym": "2018-04", "q": 15000}],
    "meta": {
        "unavailable": [],
        "note": "Volumes are allocated estimates — RRC reports production by lease, never by well.",
    },
}


class TestReports:
    """Tests for the Energy, Federal Land, and Texas report endpoints."""

    @respx.mock
    def test_energy_report(self):
        route = respx.get(f"{BASE}/energy/report").mock(
            return_value=httpx.Response(200, json=ENERGY_REPORT_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            report = ta.energy_report("25 24N 1E 6th Meridian")

        assert isinstance(report, EnergyReport)
        assert report.summary.wells_in_section == 1
        assert report.wells.in_section.rows[0].api_number == "05-123-45678"
        assert report.wells.nearby.radius_mi == 1
        assert report.royalties.scope == "county"
        assert report.constraints.split_estate.is_split_estate is True
        assert report.meta.unavailable == []
        assert route.calls[0].request.url.params["legal_location"] == "25 24N 1E 6th Meridian"

    @respx.mock
    def test_energy_report_include(self):
        route = respx.get(f"{BASE}/energy/report").mock(
            return_value=httpx.Response(200, json=ENERGY_REPORT_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            ta.energy_report("25 24N 1E 6th Meridian", include=["wells", "pipelines"])

        assert route.calls[0].request.url.params["include"] == "wells,pipelines"

    @respx.mock
    def test_federal_land_report(self):
        respx.get(f"{BASE}/federal-land/report").mock(
            return_value=httpx.Response(200, json=FEDERAL_LAND_REPORT_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            report = ta.federal_land_report("NW 25 24N 1E 6th Meridian")

        assert isinstance(report, FederalLandReport)
        assert report.report_scope == "parcel"
        assert report.surface_management.rows[0].agency == "BLM"
        assert report.flood_zones.rows[0].sfha is True
        assert report.elevation.elev_mean_m == pytest.approx(1520.4)
        assert report.meta.unavailable[0].reason == "no_state_coverage"

    @respx.mock
    def test_federal_land_report_include(self):
        route = respx.get(f"{BASE}/federal-land/report").mock(
            return_value=httpx.Response(200, json=FEDERAL_LAND_REPORT_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            ta.federal_land_report(
                "NW 25 24N 1E 6th Meridian", include=["og_leases", "flood_zones"]
            )

        assert route.calls[0].request.url.params["include"] == "og_leases,flood_zones"

    @respx.mock
    def test_texas_report(self):
        respx.get(f"{BASE}/texas/report").mock(
            return_value=httpx.Response(200, json=TEXAS_REPORT_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            report = ta.texas_report("A-175 Reeves County")

        assert isinstance(report, TexasReport)
        assert report.state == "TX"
        assert report.abstract_no == "175"
        assert report.state_leases.rows[0].lease_no == "MF123456"
        assert report.active_wells.rows[0].location.lat == pytest.approx(31.25)
        assert report.production.summary.total_cum_boe == 125000
        assert report.production.leases.rows[0].monthly[0].oil_bbl == 900

    @respx.mock
    def test_texas_production_by_location(self):
        route = respx.get(f"{BASE}/texas/production").mock(
            return_value=httpx.Response(200, json=TEXAS_PRODUCTION_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            production = ta.texas_production("A-175 Reeves County")

        assert isinstance(production, TexasProduction)
        assert production.summary.producing_lease_count == 1
        assert production.leases.rows[0].cum_boe == 125000
        assert route.calls[0].request.url.params["legal_location"] == "A-175 Reeves County"

    @respx.mock
    def test_texas_production_by_keys(self):
        route = respx.get(f"{BASE}/texas/production").mock(
            return_value=httpx.Response(200, json=TEXAS_PRODUCTION_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            ta.texas_production(county_fips="48389", abstract_no="175", block_no="4")

        params = route.calls[0].request.url.params
        assert params["county_fips"] == "48389"
        assert params["abstract_no"] == "175"
        assert params["block_no"] == "4"

    def test_texas_production_requires_input(self):
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValueError, match="legal_location or county_fips"):
                ta.texas_production()

    @respx.mock
    def test_texas_well(self):
        route = respx.get(f"{BASE}/texas/wells/42-389-32345").mock(
            return_value=httpx.Response(200, json=TEXAS_WELL_RESPONSE)
        )
        with TownshipAmerica("test-key") as ta:
            well = ta.texas_well("42-389-32345")

        assert isinstance(well, TexasWell)
        assert well.api8 == "42389323"
        assert well.units[0].denominator_basis == "time_varying"
        assert well.decline.available is True
        assert well.decline.value.b == pytest.approx(0.5)
        assert well.series_covers_all_units is True
        assert route.calls[0].request.url.path == "/texas/wells/42-389-32345"

    @respx.mock
    def test_v1_error_body_with_code(self):
        respx.get(f"{BASE}/texas/report").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": {
                        "code": "plss_not_supported",
                        "message": "PLSS not covered by the Texas API.",
                    }
                },
            )
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValidationError) as exc_info:
                ta.texas_report("NW 25 24N 1E 6th Meridian")
        assert exc_info.value.code == "plss_not_supported"
        assert exc_info.value.message == "PLSS not covered by the Texas API."

    @respx.mock
    def test_v1_not_found_with_code(self):
        respx.get(f"{BASE}/texas/wells/42389323").mock(
            return_value=httpx.Response(
                404,
                json={
                    "error": {
                        "code": "not_found",
                        "message": "No Texas well matches this API number.",
                    }
                },
            )
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(NotFoundError) as exc_info:
                ta.texas_well("42389323")
        assert exc_info.value.code == "not_found"

    @respx.mock
    def test_v1_rate_limit_with_code(self):
        respx.get(f"{BASE}/energy/report").mock(
            return_value=httpx.Response(
                429,
                json={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "You've exceeded your quota.",
                    }
                },
            )
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(RateLimitError) as exc_info:
                ta.energy_report("25 24N 1E 6th Meridian")
        assert exc_info.value.code == "rate_limit_exceeded"

    @respx.mock
    def test_legacy_error_body_keeps_code_none(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(400, json={"message": "Invalid location"})
        )
        with TownshipAmerica("test-key") as ta:
            with pytest.raises(ValidationError) as exc_info:
                ta.search("invalid")
        assert exc_info.value.code is None


class TestAsyncReports:
    """Async variants of the report endpoint tests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_energy_report(self):
        respx.get(f"{BASE}/energy/report").mock(
            return_value=httpx.Response(200, json=ENERGY_REPORT_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            report = await ta.energy_report("25 24N 1E 6th Meridian")
        assert isinstance(report, EnergyReport)
        assert report.summary.wells_in_section == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_federal_land_report(self):
        route = respx.get(f"{BASE}/federal-land/report").mock(
            return_value=httpx.Response(200, json=FEDERAL_LAND_REPORT_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            report = await ta.federal_land_report(
                "NW 25 24N 1E 6th Meridian", include=["og_leases"]
            )
        assert isinstance(report, FederalLandReport)
        assert route.calls[0].request.url.params["include"] == "og_leases"

    @respx.mock
    @pytest.mark.asyncio
    async def test_texas_report(self):
        respx.get(f"{BASE}/texas/report").mock(
            return_value=httpx.Response(200, json=TEXAS_REPORT_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            report = await ta.texas_report("A-175 Reeves County")
        assert isinstance(report, TexasReport)
        assert report.abstract_no == "175"

    @respx.mock
    @pytest.mark.asyncio
    async def test_texas_production(self):
        respx.get(f"{BASE}/texas/production").mock(
            return_value=httpx.Response(200, json=TEXAS_PRODUCTION_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            production = await ta.texas_production(
                county_fips="48389", abstract_no="175"
            )
        assert isinstance(production, TexasProduction)
        assert production.summary.total_cum_boe == 125000

    @respx.mock
    @pytest.mark.asyncio
    async def test_texas_well(self):
        respx.get(f"{BASE}/texas/wells/42389323").mock(
            return_value=httpx.Response(200, json=TEXAS_WELL_RESPONSE)
        )
        async with AsyncTownshipAmerica("test-key") as ta:
            well = await ta.texas_well("42389323")
        assert isinstance(well, TexasWell)
        assert well.decline.available is True
