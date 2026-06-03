"""Tests for the Township America MCP server tools."""

import os

import httpx
import pytest
import respx

from townshipamerica.mcp import batch_plss_convert, latlon_to_plss, plss_to_latlon

BASE = "https://developer.townshipamerica.com"

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


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Ensure the API key env var is set for all tests."""
    monkeypatch.setenv("TOWNSHIP_AMERICA_API_KEY", "test-key")


class TestPlssToLatlon:
    @respx.mock
    def test_converts_plss_to_coordinates(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        result = plss_to_latlon("NW 25 24N 1E 6th Meridian")

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2
        centroid = [f for f in result["features"] if f["properties"]["shape"] == "centroid"][0]
        assert centroid["geometry"]["coordinates"][1] == pytest.approx(41.077932)

    @respx.mock
    def test_returns_error_on_invalid_location(self):
        respx.get(f"{BASE}/search/legal-location").mock(
            return_value=httpx.Response(400, json={"message": "Invalid location"})
        )
        result = plss_to_latlon("invalid")
        assert "error" in result
        assert result["status_code"] == 400

    def test_returns_error_without_api_key(self, monkeypatch):
        monkeypatch.delenv("TOWNSHIP_AMERICA_API_KEY")
        with pytest.raises(ValueError, match="TOWNSHIP_AMERICA_API_KEY"):
            plss_to_latlon("NW 25 24N 1E 6th Meridian")


class TestLatlonToPlss:
    @respx.mock
    def test_converts_coordinates_to_plss(self):
        respx.get(f"{BASE}/search/coordinates").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        result = latlon_to_plss(latitude=41.077932, longitude=-104.01924)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2

    @respx.mock
    def test_returns_error_on_not_found(self):
        respx.get(f"{BASE}/search/coordinates").mock(
            return_value=httpx.Response(404, json={"message": "No results found"})
        )
        result = latlon_to_plss(latitude=0.0, longitude=0.0)
        assert "error" in result
        assert result["status_code"] == 404


class TestBatchPlssConvert:
    @respx.mock
    def test_batch_converts_locations(self):
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=[SEARCH_RESPONSE, SEARCH_RESPONSE])
        )
        result = batch_plss_convert(
            ["NW 25 24N 1E 6th Meridian", "NE 12 4N 5E Indian Meridian"]
        )

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["type"] == "FeatureCollection"

    @respx.mock
    def test_batch_handles_null_results(self):
        respx.post(f"{BASE}/batch/legal-location").mock(
            return_value=httpx.Response(200, json=[SEARCH_RESPONSE, None])
        )
        result = batch_plss_convert(["NW 25 24N 1E 6th Meridian", "invalid"])

        assert len(result["results"]) == 2
        assert result["results"][0] is not None
        assert result["results"][1] is None

    def test_rejects_over_100_locations(self):
        result = batch_plss_convert(["loc"] * 101)
        assert "error" in result
        assert result["status_code"] == 413
