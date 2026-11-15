# Bughouse Opening Explorer

Public web interface for the existing Ellipsoul Bughouse data platform. The site does not crawl Chess.com or rebuild the opening index. It reads a separately supplied crawler SQLite snapshot through the read-only API in `backend/` and proxies opening queries to the existing bounded opening service.

## Local development

```sh
npm install
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
```

Set `BUGHOUSE_CRAWLER_DB` to a **validated, closed/checkpointed copy** of the existing `crawler.db`. Set `OPENING_SERVICE_URL` and `OPENING_SERVICE_TOKEN` for the existing opening reader. The token is server-only; do not use a `VITE_` variable.

Run the two services in separate terminals:

```sh
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8001
npm run dev
```

The Vite development server proxies `/api/catalog` to the catalog API and `/api/opening` to the opening reader. If either data source is not configured, the interface shows an unavailable state; it does not substitute sample counts.

## Data contract and limits

- `backend/` is a read-only API over the existing crawler schema. It does not migrate or write the source database.
- The opening service supports metadata, graph neighborhoods, edge game examples, and player prefix search. It requires its validated packed artifact and its existing bearer token.
- The current opening service is position-graph based and identifies a position through graph node/state IDs. This interface begins at the indexed root and traverses moves. Direct FEN-to-node lookup is not exposed by the current reader API.
- Game records represent individual boards. A linked second board is shown only when `partner_uuid` resolves to a stored row.
- Partner board moves are replayed independently. The crawler retains links and board records, but does not provide a synchronized four-player event timeline.
- Openings are one-board statistics. Win/loss results are shown only when included in the service response.

See [deploy/README.md](deploy/README.md) for the Docker and Caddy setup.

## Deployment layout

Host this Vite frontend on a static host. Run the FastAPI catalog API on a small persistent service with a read-only mount of a validated crawler snapshot. Keep the opening reader and its multi-gigabyte artifact on a host configured for that artifact size, or use the existing authorized hosted service. Store all bearer tokens as backend secrets. Keep crawler/update jobs separate from public request serving.

The raw DB and opening artifact are not in this repository. A website deployment is not data-connected until those files/services and credentials are provisioned and the `/api/catalog/health` and `/api/opening/api/meta` endpoints have been checked.

## License

This interface is licensed under AGPL-3.0-or-later to match the existing data platform it integrates with. See `LICENSE`.
