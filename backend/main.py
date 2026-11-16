"""Read-only catalog API over the existing Bughouse crawler SQLite schema."""
from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import httpx
from bughouse_explorer.engine import Board
from bughouse_explorer.tcn import decode_tcn

app = FastAPI(title="Bughouse public catalog", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CATALOG_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
    allow_methods=["GET"], allow_headers=["*"]
)

DB_PATH = os.getenv("BUGHOUSE_CRAWLER_DB", "data/crawler.db")
OPENING_URL = os.getenv("OPENING_SERVICE_URL", "").rstrip("/")
OPENING_TOKEN = os.getenv("OPENING_SERVICE_TOKEN", "")
_stats_cache: tuple[float, dict[str, Any]] | None = None


@contextmanager
def db():
    if not os.path.isfile(DB_PATH):
        raise HTTPException(status_code=503, detail="Crawler database is not configured")
    # immutable=1 prevents SQLite from creating journals or taking write locks.
    conn = sqlite3.connect(f"file:{os.path.abspath(DB_PATH)}?mode=ro&immutable=1", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="Crawler snapshot is unavailable or has an incompatible schema") from exc
    finally:
        conn.close()


def game_select(where: str = "") -> str:
    return f"""SELECT g.uuid, g.numeric_id, g.partner_uuid, g.end_time, g.time_control,
        g.time_class, g.rated, g.url, g.tcn, g.initial_setup, g.fen,
        wp.username AS white_username, w.rating AS white_rating, w.result AS white_result,
        bp.username AS black_username, b.rating AS black_rating, b.result AS black_result
        FROM games g
        LEFT JOIN game_participants w ON w.game_uuid=g.uuid AND w.color='white'
        LEFT JOIN players wp ON wp.id=w.player_id
        LEFT JOIN game_participants b ON b.game_uuid=g.uuid AND b.color='black'
        LEFT JOIN players bp ON bp.id=b.player_id {where}"""


def _starting_board(position: str | None) -> Board:
    board = Board()
    if not position:
        return board
    fields = position.split()
    if len(fields) < 4:
        raise ValueError("initial position is not a valid FEN")
    pieces: dict[str, str] = {}
    ranks = fields[0].split("/")
    if len(ranks) != 8:
        raise ValueError("initial position has an invalid board layout")
    for row_index, row in enumerate(ranks):
        file_index = 0
        rank = 8 - row_index
        for char in row:
            if char.isdigit():
                file_index += int(char)
            else:
                if char not in "pnbrqkPNBRQK" or file_index > 7:
                    raise ValueError("initial position has an invalid piece layout")
                pieces["abcdefgh"[file_index] + str(rank)] = char
                file_index += 1
        if file_index != 8:
            raise ValueError("initial position has an invalid rank width")
    board.board = pieces
    board.white_to_move = fields[1] == "w"
    board.castling = {right: right in fields[2] for right in "KQkq"}
    board.ep = None if fields[3] == "-" else fields[3]
    return board


def public_game(row: sqlite3.Row, include_moves: bool = False) -> dict[str, Any]:
    result = dict(row)
    tcn = result.pop("tcn", None)
    if include_moves:
        try:
            raw_tcn = tcn or ""
            bounded_tcn = raw_tcn[:4096]
            if len(bounded_tcn) % 2:
                bounded_tcn = bounded_tcn[:-1]
            decoded = decode_tcn(bounded_tcn)
            moves = decoded[:2048]
            board = _starting_board(result.get("initial_setup") or result.get("fen"))
            positions = [dict(board.board)]
            for move in moves:
                board.apply(move)
                positions.append(dict(board.board))
            result["moves"] = moves
            result["positions"] = positions
            result["replay_truncated"] = len(raw_tcn) > 4096 or len(decoded) > len(moves)
        except (ValueError, KeyError, IndexError):
            result["moves"] = []
            result["positions"] = []
            result["replay_available"] = False
        else:
            result["replay_available"] = bool(moves)
    return result


@app.get("/api/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1 FROM games LIMIT 1")
    return {"status": "ready", "source": "read-only crawler snapshot"}


@app.get("/api/opening/{path:path}")
def opening_proxy(path: str, request: Request):
    """Proxy the existing bounded opening API without exposing its bearer token."""
    if not OPENING_URL or not OPENING_TOKEN:
        raise HTTPException(status_code=503, detail="Opening service is not configured")
    safe_path = path.strip("/")
    allowed = (
        safe_path == "api/meta"
        or safe_path == "api/players"
        or re.fullmatch(r"api/nodes/\d+/neighborhood", safe_path)
        or re.fullmatch(r"api/edges/\d+/games", safe_path)
    )
    if not allowed:
        raise HTTPException(status_code=404, detail="Opening API operation not found")
    # Only these bounded query values are forwarded from the browser.
    permitted = {"dataset_version", "state_id", "target_forward_depth", "max_nodes", "max_encoded_bytes", "white", "black", "edge_id", "limit", "prefix"}
    params = {key: value for key, value in request.query_params.items() if key in permitted}
    try:
        response = httpx.get(
            f"{OPENING_URL}/{safe_path}", params=params,
            headers={"Authorization": f"Bearer {OPENING_TOKEN}", "Accept": "application/json"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Opening service is unavailable") from exc
    headers = {}
    for key in ("etag", "cache-control", "retry-after", "www-authenticate"):
        if key in response.headers:
            headers[key] = response.headers[key]
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"), headers=headers)


@app.get("/api/stats")
def stats():
    global _stats_cache
    now = time.monotonic()
    if _stats_cache and now - _stats_cache[0] < 300:
        return _stats_cache[1]
    with db() as conn:
        games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        linked = conn.execute("SELECT COUNT(*) FROM games WHERE partner_uuid IS NOT NULL").fetchone()[0]
        latest = conn.execute("SELECT MAX(end_time) FROM games").fetchone()[0]
    value = {"games": games, "players": players, "linked_boards": linked, "latest_game": latest}
    _stats_cache = (now, value)
    return value


@app.get("/api/games")
def games(
    q: str | None = Query(default=None, max_length=100),
    player: str | None = Query(default=None, max_length=64),
    time_class: str | None = Query(default=None, max_length=32),
    time_control: str | None = Query(default=None, max_length=32),
    result: str | None = Query(default=None, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    clauses, params = [], []
    if q:
        # Prefix search keeps this bounded while allowing the database search box
        # to find either a board UUID or a player username.
        clauses.append("(g.uuid LIKE ? OR wp.username LIKE ? COLLATE NOCASE OR bp.username LIKE ? COLLATE NOCASE)")
        params.extend([f"{q}%", f"{q}%", f"{q}%"])
    if player:
        clauses.append("(wp.username = ? COLLATE NOCASE OR bp.username = ? COLLATE NOCASE)")
        params.extend([player, player])
    if time_class:
        clauses.append("g.time_class = ?")
        params.append(time_class)
    if time_control:
        clauses.append("g.time_control = ?")
        params.append(time_control)
    if result:
        clauses.append("(w.result = ? OR b.result = ?)")
        params.extend([result, result])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM games g LEFT JOIN game_participants w ON w.game_uuid=g.uuid AND w.color='white' LEFT JOIN players wp ON wp.id=w.player_id LEFT JOIN game_participants b ON b.game_uuid=g.uuid AND b.color='black' LEFT JOIN players bp ON bp.id=b.player_id" + where, params).fetchone()[0]
        rows = conn.execute(game_select(where) + " ORDER BY g.end_time DESC, g.uuid LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"games": [public_game(row) for row in rows], "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@app.get("/api/games/{game_uuid}")
def game_detail(game_uuid: str):
    with db() as conn:
        row = conn.execute(game_select("WHERE g.uuid = ?"), [game_uuid]).fetchone()
        if not row:
            raise HTTPException(404, "Game not found")
        game = public_game(row, include_moves=True)
        partner_id = row["partner_uuid"]
        partner = conn.execute(game_select("WHERE g.uuid = ?"), [partner_id]).fetchone() if partner_id else None
        if partner:
            game["partner"] = public_game(partner, include_moves=True)
        else:
            game["partner"] = None
    return game


@app.get("/api/players")
def players(q: str | None = Query(default=None, max_length=64), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100)):
    with db() as conn:
        if q:
            needle = f"%{q}%"
            where, params = "WHERE p.username LIKE ? COLLATE NOCASE", [needle]
        else:
            where, params = "", []
        total = conn.execute(f"SELECT COUNT(*) FROM players p {where}", params).fetchone()[0]
        rows = conn.execute(f"""SELECT p.username, p.display_username,
            COUNT(DISTINCT gp.game_uuid) AS games,
            SUM(CASE WHEN gp.result='win' THEN 1 ELSE 0 END) AS wins,
            AVG(gp.rating) AS average_rating
            FROM players p LEFT JOIN game_participants gp ON gp.player_id=p.id
            {where} GROUP BY p.id ORDER BY games DESC, p.username COLLATE NOCASE
            LIMIT ? OFFSET ?""", [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"players": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@app.get("/api/players/{username}")
def player_profile(username: str, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100)):
    with db() as conn:
        player = conn.execute("""SELECT p.id, p.username, p.display_username,
            AVG(gp.rating) AS average_rating
            FROM players p LEFT JOIN game_participants gp ON gp.player_id=p.id
            WHERE p.username=? COLLATE NOCASE GROUP BY p.id""", [username]).fetchone()
        if not player:
            raise HTTPException(404, "Player not found")
        games_total = conn.execute("SELECT COUNT(*) FROM game_participants WHERE player_id=?", [player["id"]]).fetchone()[0]
        outcomes = conn.execute("SELECT result, COUNT(*) AS n FROM game_participants WHERE player_id=? GROUP BY result", [player["id"]]).fetchall()
        rows = conn.execute(game_select("JOIN game_participants mine ON mine.game_uuid=g.uuid WHERE mine.player_id=?") + " ORDER BY g.end_time DESC LIMIT ? OFFSET ?", [player["id"], page_size, (page - 1) * page_size]).fetchall()
    return {"player": dict(player), "games": [public_game(row) for row in rows], "outcomes": {row["result"] or "unknown": row["n"] for row in outcomes}, "total": games_total, "page": page, "page_size": page_size, "pages": (games_total + page_size - 1) // page_size}

