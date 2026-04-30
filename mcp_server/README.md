# townshipamerica-mcp

Model Context Protocol (MCP) server that exposes Township America's PLSS conversion to AI agents — Claude, ChatGPT, Cursor, GitHub Copilot, Windsurf, or any MCP-compatible client.

## What you get

Six tools your AI agent can call directly:

| Tool | Purpose |
|---|---|
| `plss_to_coordinates` | Convert a PLSS legal description to GPS coordinates |
| `coordinates_to_plss` | Reverse-lookup coordinates to a PLSS description |
| `plss_to_geojson` | Return the section/quarter/aliquot polygon as GeoJSON |
| `validate_description` | Check whether a PLSS string is valid + normalized form |
| `batch_convert` | Process multiple descriptions in one call (up to 100) |
| `autocomplete` | Get suggestions for partial PLSS input |

Coverage: 30 PLSS states, 37 principal meridians. Powered by the current BLM CadNSDI V2 dataset.

## Install

```bash
pip install townshipamerica-mcp
```

You also need a Township America API key — get one free at <https://townshipamerica.com/api>.

## Configure

Set the API key in your environment:

```bash
export TOWNSHIP_AMERICA_API_KEY="ta_…"
```

## Use with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "townshipamerica": {
      "command": "townshipamerica-mcp",
      "env": {
        "TOWNSHIP_AMERICA_API_KEY": "ta_…"
      }
    }
  }
}
```

Restart Claude Desktop. Ask things like:

- *"Convert NW¼ Section 14 T2N R4E 6th Principal Meridian to GPS coordinates."*
- *"What's the PLSS legal description for 39.5501°N, -105.7821°W?"*
- *"Validate these 5 descriptions and return a JSON list."*

## Use with Cursor / Continue / VS Code

```jsonc
{
  "mcpServers": {
    "townshipamerica": {
      "command": "townshipamerica-mcp",
      "env": { "TOWNSHIP_AMERICA_API_KEY": "ta_…" }
    }
  }
}
```

## Use as a stdio MCP server (any client)

```bash
TOWNSHIP_AMERICA_API_KEY=ta_… townshipamerica-mcp
```

Communicates over stdin/stdout using the MCP protocol.

## Optional environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TOWNSHIP_AMERICA_API_KEY` | *(required)* | Your API key |
| `TOWNSHIP_AMERICA_BASE_URL` | `https://developer.townshipamerica.com` | Override the API endpoint |
| `MCP_LOG_LEVEL` | `INFO` | Log level for stderr output (DEBUG/INFO/WARNING/ERROR) |

## Pricing

The MCP server itself is free and open-source. Usage of the underlying Township America API is gated by your account plan:

- **Free tier** — 50 lookups per month
- **Pro** — Unlimited web lookups, 1K batch records / month
- **Pro+** — Everything in Pro, plus 100K REST API calls / month and priority support
- **Business / Enterprise** — Higher limits, team accounts, SLAs

See <https://townshipamerica.com/pricing>.

## Why MCP for PLSS?

PLSS legal descriptions are how the United States actually describes rural land — every BLM lease, oil & gas APD, ALTA survey, FSA acreage report, and 80% of mineral rights documents. AI agents working in those domains constantly need to convert between PLSS and GPS, and most of them resort to ChatGPT-as-calculator with measurable accuracy errors. This server gives any AI agent a reliable, BLM-CadNSDI-backed answer.

Source data: BLM CadNSDI V2, refreshed quarterly.

## License

MIT — see [LICENSE](../LICENSE).

## Links

- API: <https://townshipamerica.com/api>
- Web app: <https://townshipamerica.com>
- Issues: <https://github.com/townshipamerica/python-sdk/issues>
- MCP spec: <https://modelcontextprotocol.io>
