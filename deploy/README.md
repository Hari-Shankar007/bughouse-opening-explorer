# Deployment layout

## GitHub Pages frontend

The workflow at `.github/workflows/pages.yml` builds and publishes the Vite frontend to `https://hari-shankar007.github.io/bughouse-opening-explorer/` on pushes to `main`. In the repository, open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**. The workflow deploys the static interface; it does not host the SQLite catalog API, crawler, or packed opening artifact.

To connect live data, deploy the API using the instructions below, then set the repository Actions variable `VITE_API_ORIGIN` to that API's public HTTPS origin (for example, `https://api.example.com`). Configure `CATALOG_ALLOWED_ORIGINS` on the API to allow `https://hari-shankar007.github.io`. The bearer token remains in the API host's server environment and must not be added as a GitHub Pages variable or frontend secret.

Without `VITE_API_ORIGIN`, the public page will render with an explicit data-unavailable state. That is a frontend deployment only, not a live database deployment.

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
