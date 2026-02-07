import os
import sqlite3
import json
from flask import Flask, render_template, request
from ortools.sat.python import cp_model
from itertools import combinations
from collections import defaultdict

app = Flask(__name__)

# Инициализация на SQLite база данни
DB_PATH = "cache.db"

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
        if cached:
            LOCATIONS = [f"L{i+1}" for i in range(L)]
            result_data = {
                "rounds": cached["rounds_data"],
                "locations": LOCATIONS,
                "repeats": cached["repeats"],
                "repeats_detail": cached["repeats_detail"],
                "L": L,
                "T": T,
                "from_cache": True
            }
            return render_template("index.html", result=result_data, error=error_message)

        LOCATIONS = [f"L{i+1}" for i in range(L)]
        TEAMS = list(range(T))
        
        # Всеки отбор трябва да посети всяка локация веднъж
        # Без почиващи отбори => R = L
        ROUNDS = L

        model = cp_model.CpModel()
        
        # Променливи за двойки (всяка локация приема точно 2 отбора)
        x = {}
        for r in range(ROUNDS):
            for l in range(L):
                for i, j in combinations(TEAMS, 2):
                    x[(r, l, i, j)] = model.NewBoolVar(f"x_{r}_{l}_{i}_{j}")

        # 1️⃣ Максимум едно събитие на локация (позволява празни локации)
        for r in range(ROUNDS):
            for l in range(L):
                model.Add(sum(x[r, l, i, j] for i, j in combinations(TEAMS, 2)) <= 1)

        # 2️⃣ Всеки отбор максимум веднъж на рунд
        for r in range(ROUNDS):
            for t in TEAMS:
                pairs_with_t = sum(
                    x[r, l, i, j] for l in range(L) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                )
                model.Add(pairs_with_t <= 1)

        # 3️⃣ Всеки отбор на всяка локация точно веднъж
        for t in TEAMS:
            for l in range(L):
                pairs_on_loc = sum(
                    x[r, l, i, j] for r in range(ROUNDS) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                )
                model.Add(pairs_on_loc == 1)

        # Минимизиране на повторения на двойки
        total_repeats = []
        for i, j in combinations(TEAMS, 2):
            cnt = model.NewIntVar(0, ROUNDS, f"cnt_{i}_{j}")
            pairs_total = sum(x[r, l, i, j] for r in range(ROUNDS) for l in range(L))
            model.Add(cnt == pairs_total)
            over = model.NewIntVar(0, ROUNDS, f"over_{i}_{j}")
            model.Add(over >= cnt - 1)
            total_repeats.append(over)
        
        # Целева функция: минимизиране на повторения
        model.Minimize(sum(total_repeats))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120  # 2 минути
        import multiprocessing
        solver.parameters.num_search_workers = multiprocessing.cpu_count()

        result = solver.Solve(model)

        if result in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            rounds_data = []
            total_repeats_found = 0
            repeats_detail = []
            pair_repeat_count = defaultdict(int)

            for r in range(ROUNDS):
                row = []
                for l in range(L):
                    # Проверка за двойка
                    found_pair = [(i, j) for i, j in combinations(TEAMS, 2) if solver.Value(x[r, l, i, j])]
                    
                    if found_pair:
                        i, j = found_pair[0]
                        row.append(f"({i+1},{j+1})")
                        pair_repeat_count[(i+1, j+1)] += 1
                    else:
                        row.append("—")
                rounds_data.append(row)

            total_repeats_found = sum(v - 1 for v in pair_repeat_count.values() if v > 1)
            repeats_detail = [f"({a},{b}) – {v} пъти" for (a,b),v in pair_repeat_count.items() if v > 1]

            # 💾 Запазване на резултата в кеша
            save_result(L, T, rounds_data, total_repeats_found, repeats_detail)

            result_data = {
                "rounds": rounds_data,
                "locations": LOCATIONS,
                "repeats": total_repeats_found,
                "repeats_detail": repeats_detail,
                "L": L,
                "T": T,
                "from_cache": False
            }
        else:
            # Няма намерено решение
            error_message = f"⚠️ Не беше намерено решение за {T} отбора и {L} локации. Моля, опитайте с различни параметри."

    return render_template("index.html", result=result_data, error=error_message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render задава порта автоматично
    app.run(host="0.0.0.0", port=port)

