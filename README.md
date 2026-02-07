# 🌀 Team Rotation Optimizer

A Python-based scheduling optimizer that generates fair team rotations across multiple locations and rounds, minimizing repeated matchups. Supports flexible locations that can accommodate 2 or 3 teams simultaneously.

## ⚙️ How it works
- Input number of teams and locations.
- Mark locations as "flexible" to allow 2 or 3 teams (e.g., relay races).
- The system automatically calculates the minimal number of rounds.
- Produces a schedule showing which teams play each round and which rest.
- Minimizes repeated matchups and resting teams.

## 🚀 Run locally
1. Clone the repository  
   ```bash
   git clone https://github.com/YOUR_USERNAME/team-rotation-app.git
   cd team-rotation-app
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application
   ```bash
   python app.py
   ```

4. Open in browser
   ```
   http://localhost:5000
   ```

## 📁 Project Structure
```
team-rotation-app/
├── app.py              # Main Flask application
├── templates/
│   └── index.html      # Web interface
├── static/
│   ├── manifest.json   # PWA manifest
│   └── icons/          # App icons
├── requirements.txt    # Python dependencies
├── .render.yaml        # Render.com deployment config
└── README.md
```

## 🗄️ Database
This application **does not use a database**. All calculations are performed in-memory using Google OR-Tools constraint programming solver. Each request is stateless.

## 🛠️ Technology Stack
- **Backend**: Flask (Python web framework)
- **Optimization**: Google OR-Tools CP-SAT solver with multi-objective optimization
- **Frontend**: HTML, CSS, JavaScript (no framework)
- **Deployment**: Render.com (configured via .render.yaml)

## 📊 Example Output

**Input:** 5 teams, 2 locations (both flexible)

**Result:**
- 2 rounds (instead of 3 with regular locations)
- Location 1 hosts triple (1,2,3) in Round 1
- Location 2 hosts pair (4,5) in Round 1
- Minimal resting teams
- No repeated matchups

## 🔧 How it works
1. User inputs number of teams and locations via web form
2. User marks which locations are "flexible" (can accommodate 2 or 3 teams)
3. Flask receives the POST request
4. OR-Tools solver creates a constraint satisfaction problem with:
   - **Hard constraints**: Each team visits each location exactly once, max one event per location per round
   - **Soft constraints**: Minimize repeated matchups, minimize resting teams, prefer pairs over triples
5. Solver generates optimal schedule
6. Results are displayed in a table showing rounds, locations, and resting teams

## 🎯 Optimization Goals (Weighted)

The solver optimizes multiple objectives with priority weighting:

```
Objective = 1000 × (repeated_matchups) + 10 × (triple_events) + 1 × (resting_teams)
```

**Priority hierarchy:**
1. **Highest (weight 1000):** Minimize repeated matchups between same teams
2. **Medium (weight 10):** Prefer pairs (2 teams) over triples (3 teams) on flexible locations
3. **Lowest (weight 1):** Minimize total number of resting teams across all rounds

This means the solver will:
- Never sacrifice matchup quality to reduce resting teams
- Use triple events only when necessary (to fit schedule or avoid repeats)
- Prefer compact schedules with fewer resting teams when matchup quality is equal

## 🔒 Hard Constraints

1. **One event per location per round**: Each location hosts at most one event (pair or triple) per round
2. **One appearance per team per round**: Each team plays at most once per round
3. **Visit each location once**: Every team must visit every location exactly once throughout the schedule
4. **Flexible location capacity**: 
   - Regular locations: exactly 2 teams (pairs only)
   - Flexible locations: 2 or 3 teams (solver chooses optimally)

## ✨ Features

- **Flexible locations**: Mark locations that can host 2 or 3 teams competing simultaneously (e.g., relay races, multi-team challenges)
- **Adaptive round calculation**: Automatically computes minimum rounds needed based on teams, locations, and flexible capacity
- **No-solution handling**: Clear error message when constraints cannot be satisfied
- **Statistics display**: Shows total resting teams, average per round, and matchup repetitions
- **Multi-core solving**: Uses all available CPU cores for faster optimization (max 4 minutes timeout)
