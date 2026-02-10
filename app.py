import os
import sqlite3
import json
import time
import re
from flask import Flask, render_template, request
from ortools.sat.python import cp_model
from itertools import combinations
from collections import defaultdict

app = Flask(__name__)

MAX_VARIANTS = 5
TABLE_NAME = "results_cache_v2"

def solve_instance(locations, teams, seed, exclude_rounds=None):
    LOCATIONS = [f"L{i+1}" for i in range(locations)]
    TEAMS = list(range(teams))
    ROUNDS = locations

    model = cp_model.CpModel()

    x = {}
    for r in range(ROUNDS):
        for l in range(locations):
            for i, j in combinations(TEAMS, 2):
                x[(r, l, i, j)] = model.NewBoolVar(f"x_{r}_{l}_{i}_{j}")

    for r in range(ROUNDS):
        for l in range(locations):
            model.Add(sum(x[r, l, i, j] for i, j in combinations(TEAMS, 2)) <= 1)

    for r in range(ROUNDS):
        for t in TEAMS:
            pairs_with_t = sum(
                x[r, l, i, j] for l in range(locations) for i, j in combinations(TEAMS, 2)
                if t in (i, j)
            )
            model.Add(pairs_with_t <= 1)

    for t in TEAMS:
        for l in range(locations):
            pairs_on_loc = sum(
                x[r, l, i, j] for r in range(ROUNDS) for i, j in combinations(TEAMS, 2)
                if t in (i, j)
            )
            model.Add(pairs_on_loc == 1)

    total_repeats = []
    for i, j in combinations(TEAMS, 2):
        cnt = model.NewIntVar(0, ROUNDS, f"cnt_{i}_{j}")
        pairs_total = sum(x[r, l, i, j] for r in range(ROUNDS) for l in range(locations))
        model.Add(cnt == pairs_total)
        over = model.NewIntVar(0, ROUNDS, f"over_{i}_{j}")
        model.Add(over >= cnt - 1)
        total_repeats.append(over)

    model.Minimize(sum(total_repeats))

    if exclude_rounds is not None:
        match_literals = []
        for r in range(ROUNDS):
            for l in range(locations):
                slot = exclude_rounds[r][l]
                pair_match = re.match(r"^\((\d+),(\d+)\)$", str(slot).strip())
                if not pair_match:
                    empty = model.NewBoolVar(f"empty_{r}_{l}")
                    slot_sum = sum(x[r, l, i, j] for i, j in combinations(TEAMS, 2))
                    model.Add(slot_sum == 0).OnlyEnforceIf(empty)
                    model.Add(slot_sum >= 1).OnlyEnforceIf(empty.Not())
                    match_literals.append(empty)
                else:
                    a = int(pair_match.group(1)) - 1
                    b = int(pair_match.group(2)) - 1
                    i, j = (a, b) if a < b else (b, a)
                    match_literals.append(x[r, l, i, j])

        model.Add(sum(match_literals) <= (ROUNDS * locations) - 1)

    solver = cp_model.CpSolver()
    solver.parameters.randomize_search = True
    solver.parameters.random_seed = int(seed)
    solver.parameters.max_time_in_seconds = 120
    import multiprocessing
    solver.parameters.num_search_workers = multiprocessing.cpu_count()

    result = solver.Solve(model)
    if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    rounds_data = []
    pair_repeat_count = defaultdict(int)

    for r in range(ROUNDS):
        row = []
        for l in range(locations):
            found_pair = [(i, j) for i, j in combinations(TEAMS, 2) if solver.Value(x[r, l, i, j])]

            if found_pair:
                i, j = found_pair[0]
                row.append(f"({i+1},{j+1})")
                pair_repeat_count[(i+1, j+1)] += 1
            else:
                row.append("—")
        rounds_data.append(row)

    total_repeats_found = sum(v - 1 for v in pair_repeat_count.values() if v > 1)
    repeats_detail = [f"({a},{b}) – {v} пъти" for (a, b), v in pair_repeat_count.items() if v > 1]

    return {
        "rounds": rounds_data,
        "repeats": total_repeats_found,
        "repeats_detail": repeats_detail,
        "locations": LOCATIONS
    }

# Инициализация на SQLite база данни
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cache.db")

def init_db():
    """Създава таблица за кеширане на резултати"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            locations INTEGER NOT NULL,
            teams INTEGER NOT NULL,
            rounds_data TEXT NOT NULL,
            repeats INTEGER NOT NULL,
            repeats_detail TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cache_loc_team ON {TABLE_NAME} (locations, teams)"
    )

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='results_cache'"
    )
    has_legacy = cursor.fetchone() is not None

    if has_legacy:
        cursor.execute(f"SELECT COUNT(1) FROM {TABLE_NAME}")
        has_data = cursor.fetchone()[0] > 0
        if not has_data:
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (locations, teams, rounds_data, repeats, repeats_detail, created_at)
                SELECT locations, teams, rounds_data, repeats, repeats_detail, created_at
                FROM results_cache
            """)
    conn.commit()
    conn.close()

def get_cached_result(locations, teams):
    """Проверява дали има запазен резултат"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT id, rounds_data, repeats, repeats_detail
            FROM {TABLE_NAME}
            WHERE locations = ? AND teams = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """,
        (locations, teams)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "rounds_data": json.loads(row[1]),
            "repeats": row[2],
            "repeats_detail": json.loads(row[3])
        }
    return None

def get_cached_variants(locations, teams):
    """Връща всички вариации за дадени параметри (най-новите първо)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT id, rounds_data, repeats, repeats_detail, created_at
            FROM {TABLE_NAME}
            WHERE locations = ? AND teams = ?
            ORDER BY created_at DESC, id DESC
        """,
        (locations, teams)
    )
    rows = cursor.fetchall()
    conn.close()

    variants = []
    for row in rows:
        variants.append({
            "id": row[0],
            "rounds_data": json.loads(row[1]),
            "repeats": row[2],
            "repeats_detail": json.loads(row[3]),
            "created_at": row[4]
        })
    return variants

def get_variant_by_id(locations, teams, variant_id):
    """Връща конкретна вариация по id"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT id, rounds_data, repeats, repeats_detail
            FROM {TABLE_NAME}
            WHERE locations = ? AND teams = ? AND id = ?
        """,
        (locations, teams, variant_id)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "rounds_data": json.loads(row[1]),
            "repeats": row[2],
            "repeats_detail": json.loads(row[3])
        }
    return None

def get_cache_index():
    """Връща наличните (локации -> отбори) записи от кеша"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT locations, teams, id, created_at
            FROM {TABLE_NAME}
            ORDER BY locations ASC, teams ASC, created_at DESC, id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    index = defaultdict(lambda: defaultdict(list))
    for loc, team, variant_id, created_at in rows:
        index[loc][team].append({
            "id": variant_id,
            "created_at": created_at
        })
    return index

def save_result(locations, teams, rounds_data, repeats, repeats_detail):
    """Запазва резултат в кеша"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""INSERT INTO {TABLE_NAME} (locations, teams, rounds_data, repeats, repeats_detail)
           VALUES (?, ?, ?, ?, ?)""",
        (locations, teams, json.dumps(rounds_data), repeats, json.dumps(repeats_detail))
    )
    cursor.execute(
        f"""
            SELECT id FROM {TABLE_NAME}
            WHERE locations = ? AND teams = ?
            ORDER BY created_at DESC, id DESC
        """,
        (locations, teams)
    )
    ids = [row[0] for row in cursor.fetchall()]
    if len(ids) > MAX_VARIANTS:
        to_delete = ids[MAX_VARIANTS:]
        placeholders = ",".join("?" for _ in to_delete)
        cursor.execute(
            f"DELETE FROM {TABLE_NAME} WHERE id IN ({placeholders})",
            to_delete
        )
    conn.commit()
    conn.close()

# Инициализиране на базата при старт
init_db()

app = Flask(__name__)

@app.route("/")
def landing():
    return render_template(
        "landing.html",
        version="v1.0.1"
    )

@app.route("/generator", methods=["GET", "POST"])
def generator():
    result_data = None
    error_message = None
    cache_index = get_cache_index()
    all_variants = None
    all_locations = None
    no_more_variants = False

    allowed_locations = list(range(1, 13))
    allowed_teams = list(range(2, 25, 2))

    L_raw = request.values.get("locations")
    T_raw = request.values.get("teams")
    variant_id_raw = request.values.get("variant")
    current_variant_raw = request.form.get("current_variant_id")
    action = request.form.get("action")
    show_all = request.method == "GET" and request.args.get("show_all") == "1"

    if L_raw and T_raw:
        try:
            L = int(L_raw)
            T = int(T_raw)
            variant_id = int(variant_id_raw) if variant_id_raw else None
            current_variant_id = int(current_variant_raw) if current_variant_raw else None
        except (TypeError, ValueError):
            error_message = "⚠️ Невалидни параметри."
            return render_template(
                "index.html",
                result=result_data,
                error=error_message,
                cache_index=cache_index,
                allowed_locations=allowed_locations,
                allowed_teams=allowed_teams,
            )

        if T % 2 != 0:
            error_message = "⚠️ Броят на отборите трябва да бъде четно число."
        elif T > 2 * L:
            error_message = f"⚠️ Отборите ({T}) не могат да са повече от 2 × локации ({2*L})."

        variants = get_cached_variants(L, T)
        if not variants:
            error_message = "⚠️ Няма кеширани решения за тези параметри."

        if not error_message and variants:
            selected = None

            if variant_id:
                selected = get_variant_by_id(L, T, variant_id)
                if not selected:
                    selected = variants[0]
            elif action == "next" and current_variant_id:
                ids = [v["id"] for v in variants]
                try:
                    idx = ids.index(current_variant_id)
                except ValueError:
                    idx = 0
                if idx + 1 < len(variants):
                    selected = variants[idx + 1]
                else:
                    selected = variants[idx]
                    no_more_variants = True
            else:
                selected = variants[0]

            if show_all:
                all_variants = variants
                all_locations = [f"L{i+1}" for i in range(L)]
                result_data = None
                no_more_variants = False
            elif selected:
                LOCATIONS = [f"L{i+1}" for i in range(L)]
                result_data = {
                    "rounds": selected["rounds_data"],
                    "locations": LOCATIONS,
                    "repeats": selected["repeats"],
                    "repeats_detail": selected["repeats_detail"],
                    "L": L,
                    "T": T,
                    "variant_id": selected["id"],
                    "from_cache": True
                }

    return render_template(
        "index.html",
        result=result_data,
        error=error_message,
        cache_index=cache_index,
        allowed_locations=allowed_locations,
        allowed_teams=allowed_teams,
        no_more_variants=no_more_variants,
        all_variants=all_variants,
        all_locations=all_locations,
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render задава порта автоматично
    app.run(host="0.0.0.0", port=port)

