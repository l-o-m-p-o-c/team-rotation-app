from flask import Flask, render_template, request
from ortools.sat.python import cp_model
from itertools import combinations
from collections import defaultdict
from math import ceil

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    result_text = ""
    if request.method == "POST":
        L = int(request.form["locations"])
        T = int(request.form["teams"])

        LOCATIONS = [f"L{i+1}" for i in range(L)]
        TEAMS = list(range(T))
        R_min = max(L, ceil(T / 2))
        ROUNDS = R_min

        model = cp_model.CpModel()
        x = {}
        for r in range(ROUNDS):
            for l in range(L):
                for i, j in combinations(TEAMS, 2):
                    x[(r, l, i, j)] = model.NewBoolVar(f"x_{r}_{l}_{i}_{j}")

        # 1️⃣ Едно събитие на локация
        for r in range(ROUNDS):
            for l in range(L):
                model.Add(sum(x[r, l, i, j] for i, j in combinations(TEAMS, 2)) <= 1)

        # 2️⃣ Всеки отбор веднъж на рунд
        for r in range(ROUNDS):
            for t in TEAMS:
                model.Add(sum(
                    x[r, l, i, j] for l in range(L) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                ) <= 1)

        # 3️⃣ Всеки отбор на всяка локация веднъж
        for t in TEAMS:
            for l in range(L):
                model.Add(sum(
                    x[r, l, i, j] for r in range(ROUNDS) for i, j in combinations(TEAMS, 2)
                    if t in (i, j)
                ) == 1)

        total_repeats = []
        pair_repeat_count = defaultdict(int)
        for i, j in combinations(TEAMS, 2):
            cnt = model.NewIntVar(0, ROUNDS, f"cnt_{i}_{j}")
            model.Add(cnt == sum(x[r, l, i, j] for r in range(ROUNDS) for l in range(L)))
            over = model.NewIntVar(0, ROUNDS, f"over_{i}_{j}")
            model.Add(over >= cnt - 1)
            total_repeats.append(over)

        model.Minimize(sum(total_repeats))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        solver.parameters.num_search_workers = 8

        result = solver.Solve(model)

        if result in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            rounds_data = []
            resting_data = []
            total_repeats_found = 0
            for r in range(ROUNDS):
                row = []
                playing_teams = set()
                for l in range(L):
                    found = [(i, j) for i, j in combinations(TEAMS, 2) if solver.Value(x[r, l, i, j])]
                    if found:
                        i, j = found[0]
                        row.append(f"({i+1},{j+1})")
                        playing_teams.update([i+1, j+1])
                        pair_repeat_count[(i+1, j+1)] += 1
                    else:
                        row.append("—")
                rounds_data.append(row)
                resting = [t+1 for t in TEAMS if t+1 not in playing_teams]
                resting_data.append(resting)

            total_repeats_found = sum(v - 1 for v in pair_repeat_count.values() if v > 1)

            result_text = {
                "rounds": rounds_data,
                "resting": resting_data,
                "locations": LOCATIONS,
                "repeats": total_repeats_found,
            }
        else:
            result_text = None

    return render_template("index.html", result=result_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
