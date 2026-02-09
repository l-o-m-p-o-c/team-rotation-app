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

@app.route("/", methods=["GET", "POST"])
def index():
    result_data = None
    error_message = None
    from_cache = False

    if request.method == "GET" and request.args.get("locations") and request.args.get("teams"):
        try:
            L = int(request.args.get("locations"))
            T = int(request.args.get("teams"))
            variant_id = request.args.get("variant")
            variant_id = int(variant_id) if variant_id else None
        except (TypeError, ValueError):
            error_message = "⚠️ Невалидни параметри в линка."
            cache_index = get_cache_index()
            return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)

        cached = get_variant_by_id(L, T, variant_id) if variant_id else get_cached_result(L, T)
        if cached:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached["repeats"],
                "repeats_detail": cached["repeats_detail"],
                "L": L,
                "T": T,
                "variant_id": cached["id"],
                "from_cache": True,
                "no_other_solution": False
            }
        else:
            error_message = "⚠️ Няма кеширано решение за тези параметри."

        cache_index = get_cache_index()
        return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)
    
    if request.method == "POST":
        L = int(request.form["locations"])
        T = int(request.form["teams"])
        force_new = request.form.get("force_new") == "1"
        
        # Валидация: отборите трябва да са четен брой
        if T % 2 != 0:
            error_message = f"⚠️ Броят на отборите трябва да бъде четно число. Текущо: {T}"
            cache_index = get_cache_index()
            return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)
        
        # Валидация: отборите не могат да са повече от двойния брой локации
        if T > 2 * L:
            error_message = f"⚠️ Броят на отборите ({T}) не може да е повече от двойния брой локации (2 × {L} = {2*L})"
            cache_index = get_cache_index()
            return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)

        # 🔍 Проверка за кеширан резултат
        cached_variants = get_cached_variants(L, T)
        cached_latest = cached_variants[0] if cached_variants else None
        if cached_latest and not force_new:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached_latest["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached_latest["repeats"],
                "repeats_detail": cached_latest["repeats_detail"],
                "L": L,
                "T": T,
                "variant_id": cached_latest["id"],
                "from_cache": True,
                "no_other_solution": False
            }
            cache_index = get_cache_index()
            return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)
        cached_rounds = [v["rounds_data"] for v in cached_variants]
        max_attempts = 8 if force_new and cached_rounds else 1
        solved = None

        for attempt in range(max_attempts):
            seed = (time.time_ns() % 2147483647) + attempt
            candidate = solve_instance(L, T, seed)
            if candidate is None:
                continue
            if not cached_rounds or candidate["rounds"] not in cached_rounds:
                solved = candidate
                break

        if solved:
            save_result(L, T, solved["rounds"], solved["repeats"], solved["repeats_detail"])
            result_data = {
                "rounds": solved["rounds"],
                "locations": solved["locations"],
                "repeats": solved["repeats"],
                "repeats_detail": solved["repeats_detail"],
                "L": L,
                "T": T,
                "from_cache": False,
                "no_other_solution": False
            }
        elif cached_latest is not None:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached_latest["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached_latest["repeats"],
                "repeats_detail": cached_latest["repeats_detail"],
                "L": L,
                "T": T,
                "variant_id": cached_latest["id"],
                "from_cache": True,
                "no_other_solution": True
            }
        else:
            error_message = f"⚠️ Не беше намерено решение за {T} отбора и {L} локации. Моля, опитайте с различни параметри."

    cache_index = get_cache_index()
    return render_template("index.html", result=result_data, error=error_message, cache_index=cache_index)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render задава порта автоматично
    app.run(host="0.0.0.0", port=port)

