# Deployment layout

This project separates the public interface from the existing data operations:

1. Build `dist/` with `npm ci && npm run build`, then serve it from a static host or Caddy.
2. Run `catalog-api` from `compose.yaml` on a small persistent host. It mounts a closed, checkpointed copy of the existing crawler database read-only.
3. Set `OPENING_SERVICE_URL` and `OPENING_SERVICE_TOKEN` to an opening service you are authorized to use. The API proxy holds the token and forwards only the existing bounded metadata, node-neighborhood, edge-game, and player-search routes.
4. Keep the crawler and monthly update job in the existing data pipeline. This site never starts a crawl.

## Deploying with Caddy

- Build the frontend and place `dist/` at `/srv/bughouse-opening-explorer/dist`.
- Copy `deploy/Caddyfile.example` to the Caddy configuration, replace the example domain, and reload Caddy. It serves the single-page frontend and routes both API prefixes to the loopback-only backend.
- Put the validated database at `data/crawler.db` and create a root `.env` from `.env.example`. Keep `.env` private.
- Run `docker compose up -d --build` and check `https://your-domain/api/catalog/health`.
- Check `https://your-domain/api/opening/api/meta` only after the authorized opening URL and server token are configured.

The crawler database is not part of this repository. Copy an immutable snapshot made with SQLite's backup/checkpoint procedure; do not mount a live database whose required WAL is absent. Replacing the snapshot requires a backend restart to clear the five-minute dashboard count cache.

## Cost and capacity notes

The frontend bundle is small and fits ordinary static hosting. Catalog API storage needs a persistent disk large enough for a copy of the crawler SQLite database, and API queries can read millions of records. The opening artifact reported in the existing repository's 3 November release record was about 3.53 GB, so do not bundle it into this frontend or assume a free serverless function can host it. Reuse an authorized existing opening service, or plan separate artifact storage and a host sized for the reader. Crawler execution remains a separate scheduled workload.

The source repositories do not provide your database file, production service credentials, or a deployment account for this site. Deployment remains data-disconnected until those are supplied and the health/metadata checks pass.
