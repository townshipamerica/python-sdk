"""Tests for the Township America Python SDK client."""

import httpx
import pytest
import respx

from townshipamerica import (
    AsyncTownshipAmerica,
    AuthenticationError,
    FeatureCollection,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
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
