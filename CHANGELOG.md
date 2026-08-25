# Changelog

## 2.0.0

- New report endpoints on both clients (sync and async):
  - `energy_report(legal_location, *, include=None)` — `GET /energy/report`
  - `federal_land_report(legal_location, *, include=None)` — `GET /federal-land/report`
  - `texas_report(legal_location, *, include=None)` — `GET /texas/report`
  - `texas_production(legal_location=None, *, county_fips=None, abstract_no=None, block_no=None)` — `GET /texas/production`
  - `texas_well(api)` — `GET /texas/wells/{api}` (API-8 or API-14)
- New pydantic models for the reports (`EnergyReport`, `FederalLandReport`,
  `TexasReport`, `TexasProduction`, `TexasWell`, `SectionEnvelope`,
  `ReportMeta`, and per-section row models), re-exported from `townshipamerica`
- BREAKING: exceptions gained a `code` attribute (keyword parameter on the
  constructors); v1 error bodies `{"error": {"code", "message"}}` are now
  parsed into `.message`/`.code` before the legacy `message` fallback

## 0.1.0 (Unreleased)

- Initial release
- Sync and async clients for all API endpoints: search, reverse, autocomplete, batch_search, batch_reverse
- Pydantic v2 models for GeoJSON responses with convenience properties
- Typed exceptions mapped to HTTP status codes
- Python 3.9–3.13 support
