import os
import pandas as pd
import sqlite3
from typing import Optional
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, inspect

app = FastAPI(title="Bundesliga Analytics")

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "my_database.db")
SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
TEAMS_INFO_PATH = os.path.join(SAMPLE_DATA_DIR, "teams_info.csv")
TABLE_PATH = os.path.join(SAMPLE_DATA_DIR, "table.csv")


# Database engine
# Database engine - use environment variable for Render, fallback to local SQLite
DATABASE_URL = os.environ.get('DATABASE_URL', f"sqlite:///{DATABASE_PATH}")

# Fix for Render's PostgreSQL URL format
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)


# Templates and Static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request, "page_title": "Home"})
    except Exception as e:
        return f"<h1>Template Error</h1><pre>{e}</pre>"

@app.get("/players", response_class=HTMLResponse)
async def top_scorers(
    request: Request, 
    minutes: int = Query(15, alias="minutes"),
    after_mins: int = Query(75, alias="after_mins")
):
    query_before = """
        SELECT scorer_name, COUNT(*) AS goal_count
        FROM goals
        WHERE minute < :mins
        GROUP BY scorer_name
        ORDER BY goal_count DESC
        LIMIT 15
    """
    df_before = pd.read_sql(query_before, engine, params={'mins': minutes})
    data_before = df_before.to_dict(orient='records')

    query_after = """
        SELECT scorer_name, COUNT(*) AS goal_count
        FROM goals
        WHERE minute > :mins
        GROUP BY scorer_name
        ORDER BY goal_count DESC
        LIMIT 15
    """
    df_after = pd.read_sql(query_after, engine, params={'mins': after_mins})
    data_after = df_after.to_dict(orient='records')

    context = {
        "request": request,
        "scorers_before": data_before,
        "scorers_after": data_after,
        "current_mins": minutes,
        "current_after_mins": after_mins,
        "page_title": "Players"
    }

    # If it's an HTMX request, return only the partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/players_table.html", context)
    
    return templates.TemplateResponse("players.html", context)

@app.get("/referees", response_class=HTMLResponse)
async def referees(request: Request, view: str = "average"):
    if view == 'total':
        query = """
            SELECT referees.ref_name, SUM(match_cum_agg_stats.totalTotal_Cards) AS metric
            FROM match_cum_agg_stats
            JOIN matches ON match_cum_agg_stats.WS_match_id = matches.WS_match_id
            JOIN referees ON referees.ref_code = matches.refereeCode
            GROUP BY referees.ref_code, referees.ref_name
            ORDER BY metric DESC;
        """
        label = "Total cards"
    elif view == 'red':
        query = """
            SELECT referees.ref_name, SUM(match_cum_agg_stats.totalRed_Cards) AS metric
            FROM match_cum_agg_stats
            JOIN matches ON match_cum_agg_stats.WS_match_id = matches.WS_match_id
            JOIN referees ON referees.ref_code = matches.refereeCode
            GROUP BY referees.ref_code, referees.ref_name
            ORDER BY metric DESC;
        """
        label = "Total red cards"
    else:
        query = """
            SELECT referees.ref_name,
                   ROUND(SUM(match_cum_agg_stats.totalTotal_Cards) * 1.0 / COUNT(match_cum_agg_stats.WS_match_id), 2) AS metric
            FROM match_cum_agg_stats
            JOIN matches ON match_cum_agg_stats.WS_match_id = matches.WS_match_id
            JOIN referees ON referees.ref_code = matches.refereeCode
            GROUP BY referees.ref_code, referees.ref_name
            ORDER BY metric DESC;
        """
        label = "Cards per game"

    df = pd.read_sql(query, engine)
    data = df.to_dict(orient='records')

    context = {
        "request": request,
        "referees": data,
        "current_view": view,
        "metric_label": label,
        "page_title": "Referees"
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/referees_table.html", context)

    return templates.TemplateResponse("referees.html", context)

@app.get("/db-status")
async def db_status():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    status = []
    for table in tables:
        count = pd.read_sql(f"SELECT COUNT(*) FROM {table}", engine).iloc[0, 0]
        status.append({
            "table_name": table,
            "row_count": int(count)
        })

    return {
        "database": "my_database.db",
        "tables": status,
        "location": DATABASE_PATH
    }

@app.get("/teams", response_class=HTMLResponse)
async def teams_home(request: Request):
    teams_list = [
        "Bremen", "Bayern", "Leverkusen", "Leipzig", "Wolfsburg",
        "Heidenheim", "Hoffenheim", "Freiburg", "Augsburg", "Gladbach",
        "Stuttgart", "Bochum", "Dortmund", "Cologne", "Union",
        "Mainz", "Frankfurt", "Darmstadt"
    ]
    teams_list = sorted(teams_list)
    return templates.TemplateResponse("teams.html", {
        "request": request, 
        "teams": teams_list, 
        "page_title": "Teams"
    })


@app.get("/teams/{team_name}", response_class=HTMLResponse)
async def team_detail(request: Request, team_name: str):
    query = """
    SELECT g.scorer_name, COUNT(*) AS goal_count
    FROM goals g
    JOIN teams t ON g.team_code = t.team_code
    WHERE t.team_name = :team_name
    GROUP BY g.scorer_name
    ORDER BY goal_count DESC
    LIMIT 1;
    """

    df_result = pd.read_sql(query, engine, params={'team_name': team_name})
    if not df_result.empty:
        top_player = df_result.iloc[0]['scorer_name']
        goals = df_result.iloc[0]['goal_count']
    else:
        top_player = "No data"
        goals = 0


    try:
        df_info = pd.read_csv(TEAMS_INFO_PATH, encoding='latin-1')
        df_info['team_name'] = df_info['team_name'].str.strip()
        team_info = df_info[df_info['team_name'] == team_name].iloc[0]

        df_table = pd.read_csv(TABLE_PATH)
        df_table.columns = df_table.columns.str.strip()
        df_table['Team'] = df_table['Team'].str.strip()
        team_table = df_table[df_table['Team'] == team_name].iloc[0]

        context = {
            "request": request,
            "team": team_name,
            "player": top_player,
            "goals": goals,
            "page_title": "Team page",
            "established": team_info['established'],
            "stadium": team_info['stadium'],
            "capacity": team_info['capacity'],
            "position": team_table['Pos'],
            "wins": team_table['W'],
            "goals_scored": team_table['GF']
        }
    except Exception as e:
        # Fallback if CSVs are missing or mismatch
        context = {
            "request": request,
            "team": team_name,
            "player": top_player,
            "goals": goals,
            "page_title": "Team page (Data Error)",
            "established": "N/A",
            "stadium": "N/A",
            "capacity": "N/A",
            "position": "N/A",
            "wins": "N/A",
            "goals_scored": "N/A"
        }

    return templates.TemplateResponse("team_detail.html", context)

@app.get("/matches", response_class=HTMLResponse)
async def match_outliers(
    request: Request,
    stat: str = Query("totalGoals"),
    team_stat: str = Query("Goals")
):
    stats = {
        "totalGoals": "Total goals",
        "totalShots": "Total shots",
        "totalShots_on_target": "Total shots on target",
        "totalWoodwork_shots":"Total woodwork shots",
        "totalPenalty_shots":"Total penalties",
        "totalFouls":"Total fouls",
        "totalTotal_Cards":"Total cards",
        "totalRed_Cards":"Total red cards",
        "totalDribbles_won":"Total successful dribbles",
        "totalLong_Balls":"Total long balls",
        "totalAerials":"Total aerial duels",
        "totalTackles_Attempted":"Total tackles"
    }

    team_stats = {
        "Goals": "Goals",
        "Shots": "Shots",
        "Shots_on_target": "Shots on target",
        "Shots_off_Target_b":"Off-target shots",
        "Conversion_Rate_percent":"Shot conversion rate (%)",
        "Penalty_shots":"Penalties",
        "Outside_of_box_shots":"Shots from outside the box",
        "Left_foot_shots":"Left-foot shots",
        "Headed_shots":"Headed shots",
        "Fouls": "Fouls",
        "Total_Cards":"Cards",
        "Total_Passes":"Passes",
        "Crosses":"Crosses",
        "Long_Balls":"Long balls",
        "Average_Pass_Streak":"Average pass streak",
        "Possession_percent":"Possession (%)",
        "Pass_Success_percent":"Pass accuracy (%)",
        "Dribbles_won":"Successful dribbles",
        "Aerial_Duel_Success_percent":"Aerial duel success (%)",
        "Offsides":"Offsides",
    }

    if stat not in stats:
        stat = "totalGoals"

    if team_stat not in team_stats:
        team_stat = "Goals"


    query1 = f"""
        SELECT m.Match_name, s.{stat}
        FROM match_cum_agg_stats s
        JOIN matches m ON s.WS_match_id = m.WS_match_id
        ORDER BY s.{stat} DESC
        LIMIT 10
    """
    
    query2 = f"""
        SELECT m.Match_name, t.team_name, s.{team_stat}
        FROM team_match_stats s
        JOIN matches m ON s.match_id = m.WS_match_id
        JOIN teams t ON s.Team_Code = t.team_code
        ORDER BY s.{team_stat} DESC
        LIMIT 10
    """

    try:
        df1 = pd.read_sql(query1, engine)
        results1 = [tuple(x) for x in df1.to_numpy()]
    except Exception as e:
        results1 = [("Error loading data", 0)]
    
    try:
        df2 = pd.read_sql(query2, engine)
        results2 = [tuple(x) for x in df2.to_numpy()]
    except Exception as e:
        results2 = [("Error loading data", "Error", 0)]

    
    context = {
        "request": request,
        "stats": stats,
        "team_stats": team_stats,
        "selected_stat": stat,
        "selected_team_stat": team_stat,
        "results1": results1,
        "results2": results2,
        "page_title": "Matches"
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/matches_content.html", context)

    return templates.TemplateResponse("matches.html", context)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
