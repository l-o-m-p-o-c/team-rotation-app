# 🌀 Team Rotation Optimizer (v1-simple)

**Simplified version** - A Python-based scheduling optimizer that generates fair team rotations across multiple locations and rounds, minimizing repeated matchups.

## ⚙️ How it works
- Input number of teams (even number) and locations.
- Each location hosts maximum 2 teams per round (can be empty).
- Number of teams must not exceed 2 × number of locations.
- No resting teams - all teams play every round.
- Some locations may remain empty if teams < 2 × locations.
- Minimizes repeated matchups between teams.

## 🔒 Constraints

**Hard constraints:**
- Each team visits each location exactly once
- Each location hosts maximum 1 pair (2 teams) per round (can be empty)
- Teams count must be even number
- Teams ≤ 2 × Locations

**Soft constraints:**
- Minimize repeated matchups between same teams

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
This application uses **SQLite** for caching optimization results. Results are stored locally in `cache.db` and reused when the same team/location combination is requested again.

**Cache behavior:**
- First request: Computes solution using OR-Tools (~2-5 seconds)
- Subsequent requests: Loads from cache (~0.001 seconds for DB access)
- Cache persists between sessions and restarts
- Shared across all users when deployed

**Cache file:** `cache.db` (created automatically on first run)

## 🛠️ Technology Stack
- **Backend**: Flask (Python web framework)
- **Optimization**: Google OR-Tools CP-SAT solver
- **Frontend**: HTML, CSS, JavaScript (no framework)

## 📊 Example Output

**Input:** 6 teams, 3 locations

**Result:**
- 3 rounds (each team visits each location once)
- All teams play every round (6 teams = 2 × 3 locations)
- No empty locations
- Minimal repeated matchups

**Input:** 4 teams, 3 locations

**Result:**
- 3 rounds
- All teams play every round
- One location remains empty each round (4 teams = 2 pairs, 3 locations)
- Minimal repeated matchups

## 🔧 How it works
1. User inputs number of teams (even) and locations via web form
2. Validates: teams is even, teams ≤ 2 × locations
3. **Checks SQLite cache** for existing solution with same parameters
4. If cached: Returns result instantly (⚡ indicator shown)
5. If not cached: Flask receives the POST request and calls OR-Tools solver
6. OR-Tools solver creates a constraint satisfaction problem with:
   - **Hard constraints**: Each team visits each location exactly once, maximum 1 pair per location per round (locations can be empty)
   - **Soft constraint**: Minimize repeated matchups
7. Solver generates optimal schedule
8. **Result is saved to cache** for future requests
9. Results are displayed in a table showing rounds and locations (empty locations shown as "—")

## 🚀 Deploy to Render.com

**Quick Deploy:**

1. Push your code to GitHub
   ```bash
   git push origin v1-simple
   ```

2. Go to [render.com](https://render.com) and sign in with GitHub

3. Click **"New +"** → **"Web Service"**

4. Connect your repository: `team-rotation-app`

5. Render will auto-detect `.render.yaml` configuration

6. Click **"Create Web Service"**

7. Wait for deployment (~2-3 minutes)

8. Your app will be live at `https://team-rotation-app.onrender.com`

**Important:** The free plan includes:
- ✅ Persistent disk for SQLite (cache preserved)
- ✅ HTTPS/SSL automatically
- ✅ Custom domain support
- ⚠️ Sleeps after 15 min of inactivity (first request takes ~30s)

**For production:**
- Upgrade to paid plan ($7/month) for always-on service
- Or use Railway.app (similar setup, different pricing)
