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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results_cache (
            locations INTEGER NOT NULL,
            teams INTEGER NOT NULL,
            rounds_data TEXT NOT NULL,
            repeats INTEGER NOT NULL,
            repeats_detail TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (locations, teams)
        )
    """)
    conn.commit()
    conn.close()

def get_cached_result(locations, teams):
    """Проверява дали има запазен резултат"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rounds_data, repeats, repeats_detail FROM results_cache WHERE locations = ? AND teams = ?",
        (locations, teams)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "rounds_data": json.loads(row[0]),
            "repeats": row[1],
            "repeats_detail": json.loads(row[2])
        }
    return None

def save_result(locations, teams, rounds_data, repeats, repeats_detail):
    """Запазва резултат в кеша"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR REPLACE INTO results_cache (locations, teams, rounds_data, repeats, repeats_detail)
           VALUES (?, ?, ?, ?, ?)""",
        (locations, teams, json.dumps(rounds_data), repeats, json.dumps(repeats_detail))
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
    
    if request.method == "POST":
        L = int(request.form["locations"])
        T = int(request.form["teams"])
        force_new = request.form.get("force_new") == "1"
        
        # Валидация: отборите трябва да са четен брой
        if T % 2 != 0:
            error_message = f"⚠️ Броят на отборите трябва да бъде четно число. Текущо: {T}"
            return render_template("index.html", result=result_data, error=error_message)
        
        # Валидация: отборите не могат да са повече от двойния брой локации
        if T > 2 * L:
            error_message = f"⚠️ Броят на отборите ({T}) не може да е повече от двойния брой локации (2 × {L} = {2*L})"
            return render_template("index.html", result=result_data, error=error_message)

        # 🔍 Проверка за кеширан резултат
        cached = get_cached_result(L, T)
        if cached and not force_new:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached["repeats"],
                "repeats_detail": cached["repeats_detail"],
                "L": L,
                "T": T,
                "from_cache": True,
                "no_other_solution": False
            }
            return render_template("index.html", result=result_data, error=error_message)
        cached_rounds = cached["rounds_data"] if cached else None
        max_attempts = 8 if force_new and cached_rounds is not None else 1
        solved = None

        for attempt in range(max_attempts):
            seed = (time.time_ns() % 2147483647) + attempt
            candidate = solve_instance(L, T, seed, exclude_rounds=cached_rounds if force_new else None)
            if candidate is None:
                continue
            if cached_rounds is None or candidate["rounds"] != cached_rounds:
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
        elif cached_rounds is not None:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached["repeats"],
                "repeats_detail": cached["repeats_detail"],
                "L": L,
                "T": T,
                "from_cache": True,
                "no_other_solution": True
            }
        else:
            error_message = f"⚠️ Не беше намерено решение за {T} отбора и {L} локации. Моля, опитайте с различни параметри."

    return render_template("index.html", result=result_data, error=error_message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render задава порта автоматично
    app.run(host="0.0.0.0", port=port)

