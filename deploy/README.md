# Deployment layout

## GitHub Pages frontend

The workflow at `.github/workflows/pages.yml` builds and publishes the Vite frontend to `https://hari-shankar007.github.io/bughouse-opening-explorer/`. GitHub Pages serves only the static frontend; it does not run the FastAPI service or store SQLite files.

The Opening page uses the FastAPI proxy already in this repository to query Ellipsoul’s existing hosted position index. It needs no crawler snapshot for opening counts. Deploy the existing `backend/` service, set `OPENING_SERVICE_URL=https://bughouse.aronteh.com/api/opening-explorer`, and set `CATALOG_ALLOWED_ORIGINS=https://hari-shankar007.github.io`. The public upstream route does not require an incoming bearer token; leave `OPENING_SERVICE_TOKEN` blank unless your authorized upstream requires one. Then set the GitHub Actions repository variable `VITE_API_ORIGIN` to the deployed FastAPI HTTPS origin. No private token belongs in a GitHub Pages variable.

The current public position index reports about seven million accepted games. The proxy passes only the bounded metadata, neighborhood, edge-game, and player-prefix requests supported by the existing service. The upstream interface itself cannot be embedded in this site, so the site renders its own board and continuation list.

## Game and player catalog

To enable `/api/catalog` game searches and player profiles, also mount an authorized, closed/checkpointed crawler SQLite snapshot at `BUGHOUSE_CRAWLER_DB`. That raw database is not in either GitHub repository. Opening-position counts can work without it; full game/player catalog results cannot.

## Deployment steps

1. Deploy the existing FastAPI application in `backend/` on a persistent HTTPS host. The backend may serve opening queries without a crawler DB snapshot.
2. Configure `OPENING_SERVICE_URL`, `CATALOG_ALLOWED_ORIGINS`, and optional server-side `OPENING_SERVICE_TOKEN` on that host.
3. Set the repository Actions variable `VITE_API_ORIGIN` to the backend origin and push/re-run the Pages workflow.
4. Verify `https://<api-host>/api/opening/api/meta` returns dataset metadata and `https://<api-host>/api/opening/api/nodes/<root-node>/neighborhood?...` returns graph continuations.
5. For game/player routes only, mount the validated crawler snapshot and restart the backend.

The crawler and monthly refresh process remain separate. This site does not start a second crawler or rewrite the existing opening index.

