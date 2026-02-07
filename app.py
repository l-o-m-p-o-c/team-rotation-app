import os
from flask import Flask, render_template, request
from ortools.sat.python import cp_model
from itertools import combinations
from collections import defaultdict
from math import ceil

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    result_data = None
    error_message = None
    if request.method == "POST":
        L = int(request.form["locations"])
        T = int(request.form["teams"])
        
        # Получаване на гъвкави локации
        flexible_locations = request.form.getlist("flexible")
        flexible_set = set(int(x) - 1 for x in flexible_locations)  # 0-indexed

        LOCATIONS = [f"L{i+1}" for i in range(L)]
        TEAMS = list(range(T))
        
        # Изчисляване на минимален брой рундове с отчитане на гъвкави локации
        max_teams_per_round = 0
        for l in range(L):
            if l in flexible_set:
                max_teams_per_round += 3  # Гъвкава локация може 3 отбора
            else:
                max_teams_per_round += 2  # Обикновена локация може 2 отбора
        
        # Не може повече отбори от общия брой на рунд
        max_teams_per_round = min(max_teams_per_round, T)
        
        # Всеки отбор трябва да посети L локации
        # Общо посещения = T × L
        # На рунд можем max_teams_per_round посещения
        R_min = max(L, ceil((T * L) / max_teams_per_round))
        ROUNDS = R_min

        model = cp_model.CpModel()
        
        # Променливи за двойки (всички локации)
        x = {}
        for r in range(ROUNDS):
            for l in range(L):
                for i, j in combinations(TEAMS, 2):
                    x[(r, l, i, j)] = model.NewBoolVar(f"x_{r}_{l}_{i}_{j}")
        
        # Променливи за тройки (само гъвкави локации)
        y = {}
        for r in range(ROUNDS):
            for l in flexible_set:
                for i, j, k in combinations(TEAMS, 3):
                    y[(r, l, i, j, k)] = model.NewBoolVar(f"y_{r}_{l}_{i}_{j}_{k}")

        # 1️⃣ Едно събитие на локация (двойка ИЛИ тройка)
        for r in range(ROUNDS):
            for l in range(L):
                pairs = sum(x[r, l, i, j] for i, j in combinations(TEAMS, 2))
                if l in flexible_set:
                    triples = sum(y[r, l, i, j, k] for i, j, k in combinations(TEAMS, 3))
                    model.Add(pairs + triples <= 1)
                else:
                    model.Add(pairs <= 1)

        # 2️⃣ Всеки отбор веднъж на рунд
        for r in range(ROUNDS):
            for t in TEAMS:
                pairs_with_t = sum(
                    x[r, l, i, j] for l in range(L) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                )
                triples_with_t = sum(
                    y[r, l, i, j, k] for l in flexible_set for i, j, k in combinations(TEAMS, 3)
                    if t in (i, j, k)
                )
                model.Add(pairs_with_t + triples_with_t <= 1)

        # 3️⃣ Всеки отбор на всяка локация веднъж
        for t in TEAMS:
            for l in range(L):
                pairs_on_loc = sum(
                    x[r, l, i, j] for r in range(ROUNDS) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                )
                if l in flexible_set:
                    triples_on_loc = sum(
                        y[r, l, i, j, k] for r in range(ROUNDS) for i, j, k in combinations(TEAMS, 3)
                        if t in (i, j, k)
                    )
                    model.Add(pairs_on_loc + triples_on_loc == 1)
                else:
                    model.Add(pairs_on_loc == 1)

        total_repeats = []
        pair_repeat_count = defaultdict(int)
        
        # Минимизиране на повторения за двойки
        for i, j in combinations(TEAMS, 2):
            cnt = model.NewIntVar(0, ROUNDS, f"cnt_{i}_{j}")
            pairs_total = sum(x[r, l, i, j] for r in range(ROUNDS) for l in range(L))
            model.Add(cnt == pairs_total)
            over = model.NewIntVar(0, ROUNDS, f"over_{i}_{j}")
            model.Add(over >= cnt - 1)
            total_repeats.append(over)
        
        # Минимизиране на повторения за тройки
        for i, j, k in combinations(TEAMS, 3):
            if flexible_set:  # Само ако има гъвкави локации
                cnt = model.NewIntVar(0, ROUNDS, f"cnt3_{i}_{j}_{k}")
                triples_total = sum(y[r, l, i, j, k] for r in range(ROUNDS) for l in flexible_set)
                model.Add(cnt == triples_total)
                over = model.NewIntVar(0, ROUNDS, f"over3_{i}_{j}_{k}")
                model.Add(over >= cnt - 1)
                total_repeats.append(over)

        # 📊 Минимизиране на почиващи отбори
        total_resting = []
        for r in range(ROUNDS):
            for t in TEAMS:
                is_resting = model.NewBoolVar(f"rest_{r}_{t}")
                # Отборът почива ако не играе в този рунд
                pairs_with_t = sum(
                    x[r, l, i, j] for l in range(L) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                )
                triples_with_t = sum(
                    y[r, l, i, j, k] for l in flexible_set for i, j, k in combinations(TEAMS, 3)
                    if t in (i, j, k)
                )
                # is_resting е 1 ако отборът не играе (сумата е 0)
                model.Add(pairs_with_t + triples_with_t == 0).OnlyEnforceIf(is_resting)
                model.Add(pairs_with_t + triples_with_t >= 1).OnlyEnforceIf(is_resting.Not())
                total_resting.append(is_resting)

        # 🔢 Минимизиране на използването на тройки (предпочитание за двойки)
        total_triples = []
        if flexible_set:
            for r in range(ROUNDS):
                for l in flexible_set:
                    for i, j, k in combinations(TEAMS, 3):
                        total_triples.append(y[r, l, i, j, k])

        # Комбинирана целева функция с тегла
        # Приоритет 1: минимизиране на повторения (тегло 1000)
        # Приоритет 2: минимизиране на тройки (тегло 10) - предпочитане на двойки
        # Приоритет 3: минимизиране на почиващи (тегло 1)
        objective = 1000 * sum(total_repeats) + 10 * sum(total_triples) + sum(total_resting)
        model.Minimize(objective)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 240  # ⏱ увеличено време до 4 минути
        import multiprocessing
        solver.parameters.num_search_workers = multiprocessing.cpu_count()


        result = solver.Solve(model)

        if result in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            rounds_data = []
            resting_data = []
            total_repeats_found = 0
            repeats_detail = []

            for r in range(ROUNDS):
                row = []
                playing_teams = set()

                for l in range(L):
                    # Проверка за двойка
                    found_pair = [(i, j) for i, j in combinations(TEAMS, 2) if solver.Value(x[r, l, i, j])]
                    # Проверка за тройка (само ако локацията е гъвкава)
                    found_triple = []
                    if l in flexible_set:
                        found_triple = [(i, j, k) for i, j, k in combinations(TEAMS, 3) if solver.Value(y[r, l, i, j, k])]
                    
                    if found_triple:
                        i, j, k = found_triple[0]
                        row.append(f"({i+1},{j+1},{k+1})")
                        playing_teams.update([i+1, j+1, k+1])
                    elif found_pair:
                        i, j = found_pair[0]
                        row.append(f"({i+1},{j+1})")
                        playing_teams.update([i+1, j+1])
                        pair_repeat_count[(i+1, j+1)] += 1
                    else:
                        row.append("—")
                rounds_data.append(row)
                resting = [t+1 for t in TEAMS if t+1 not in playing_teams]
                resting_data.append(resting)

            total_repeats_found = sum(v - 1 for v in pair_repeat_count.values() if v > 1)
            repeats_detail = [f"({a},{b}) – {v} пъти" for (a,b),v in pair_repeat_count.items() if v > 1]
            
            # Изчисляване на общ брой почиващи
            total_resting_count = sum(len(r) for r in resting_data)
            avg_resting = total_resting_count / ROUNDS if ROUNDS > 0 else 0

            result_data = {
                "rounds": rounds_data,
                "resting": resting_data,
                "locations": LOCATIONS,
                "repeats": total_repeats_found,
                "repeats_detail": repeats_detail,
                "L": L,
                "T": T,
                "flexible": [f"L{i+1}" for i in flexible_set],
                "total_resting": total_resting_count,
                "avg_resting": round(avg_resting, 1)
            }
        else:
            # Няма намерено решение
            error_message = f"⚠️ Не беше намерено решение за {T} отбора и {L} локации. Моля, опитайте с различни параметри."

    return render_template("index.html", result=result_data, error=error_message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render задава порта автоматично
    app.run(host="0.0.0.0", port=port)

