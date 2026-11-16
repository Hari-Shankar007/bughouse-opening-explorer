# Bughouse Opening Explorer

Public web interface for the existing Ellipsoul Bughouse data platform. The site reuses the existing hosted position index and its read-only query service; it does not crawl Chess.com or rebuild the opening index. The existing FastAPI proxy in `backend/` forwards bounded opening queries without copying the packed multi-gigabyte artifact.

## Local development

```sh
npm install
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
```

Copy `.env.example` to `.env`. The default `OPENING_SERVICE_URL` points at Ellipsoul’s hosted opening-index route. A bearer token is optional for that public route and remains server-side if your upstream requires one. The `BUGHOUSE_CRAWLER_DB` snapshot is needed only for the separate game and player catalog endpoints.

Run the existing API and frontend in separate terminals:

```sh
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8001
npm run dev
```

The Vite development server proxies `/api/catalog` and `/api/opening` to the API. In production, set the GitHub Actions repository variable `VITE_API_ORIGIN` to the public HTTPS origin of this existing FastAPI proxy. GitHub Pages cannot host that Python service.

## Opening data behavior

- The opening page navigates the existing position graph and shows indexed game support plus the most-played continuations, sorted by count. Recorded drop moves appear where present in the graph.
- The service identifies positions through graph node/state IDs. This interface reaches positions by following moves; the current service does not expose arbitrary FEN-to-node lookup.
- Opening counts are board-local. A drop may be counted as a move at a position, but the index does not establish which partner-board capture supplied a historical drop.
- Interactive Analysis is hypothetical and local. Captures transfer pieces between the two analysis boards’ pockets; this does not alter historical statistics or establish historical transfer timing. The editor does not enforce full Bughouse legality.

## Game catalog data

The read-only API in `backend/` can serve the existing crawler schema when `BUGHOUSE_CRAWLER_DB` points to an authorized, closed/checkpointed snapshot. The raw crawler database is not published in either GitHub repository. Games and player profiles therefore need a separately hosted snapshot; opening-position counts do not.

See [deploy/README.md](deploy/README.md) for deployment configuration. Keep `OPENING_SERVICE_TOKEN` and any database credentials on the API host; never place them in `VITE_` variables.

## License

This interface is licensed under AGPL-3.0-or-later to match the existing data platform it integrates with. See `LICENSE`.

