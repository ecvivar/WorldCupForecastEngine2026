#!/bin/bash
# =============================================================================
# WorldCup Forecast Engine 2026 — Docker Entrypoint
# =============================================================================
set -e

echo "=== WorldCup Forecast Engine — Startup ==="

# --- Wait for PostgreSQL ---
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL..."
    python -c "
import time, sys
from sqlalchemy import create_engine, text
url = '$DATABASE_URL'
for i in range(30):
    try:
        e = create_engine(url)
        e.connect().execute(text('SELECT 1'))
        e.dispose()
        print('PostgreSQL is ready')
        sys.exit(0)
    except Exception as ex:
        print(f'  Waiting for DB ({i+1}/30): {ex}')
        time.sleep(2)
print('ERROR: PostgreSQL not available after 60s')
sys.exit(1)
"
fi

# --- Create tables ---
echo "Creating database tables..."
python -c "
from app.db.session import engine, Base
from app.models import team, match, group, group_standing, competition, elo_rating, fifa_ranking, player, simulation, xg_metrics
Base.metadata.create_all(bind=engine)
print('Tables created successfully')
"

# --- Seed data (idempotent) ---
echo "Seeding initial data..."
python -c "
import uuid
from datetime import date, datetime, timedelta
from app.db.session import SessionLocal
from app.models.competition import Competition
from app.models.team import Team
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.match import Match
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.xg_metrics import XGMetrics

db = SessionLocal()
try:
    exists = db.query(Competition).count()
    if exists > 0:
        print(f'Database already has {exists} competition(s), skipping seed')
        db.close()
    else:
        OFFICIAL_GROUPS = {
            'A': ['México', 'Sudáfrica', 'Corea del Sur', 'República Checa'],
            'B': ['Canadá', 'Bosnia-Herzegovina', 'Qatar', 'Suiza'],
            'C': ['Brasil', 'Marruecos', 'Haití', 'Escocia'],
            'D': ['Estados Unidos', 'Paraguay', 'Australia', 'Turquía'],
            'E': ['Alemania', 'Curazao', 'Costa de Marfil', 'Ecuador'],
            'F': ['Países Bajos', 'Japón', 'Suecia', 'Túnez'],
            'G': ['Bélgica', 'Egipto', 'Irán', 'Nueva Zelanda'],
            'H': ['España', 'Cabo Verde', 'Arabia Saudita', 'Uruguay'],
            'I': ['Francia', 'Senegal', 'Irak', 'Noruega'],
            'J': ['Argentina', 'Argelia', 'Austria', 'Jordania'],
            'K': ['Portugal', 'RD Congo', 'Uzbekistán', 'Colombia'],
            'L': ['Inglaterra', 'Croacia', 'Ghana', 'Panamá'],
        }
        TEAM_META = {
            'Argentina': ('ARG', 'South America', 1900), 'Brasil': ('BRA', 'South America', 1914),
            'Francia': ('FRA', 'Europe', 1904), 'Inglaterra': ('ENG', 'Europe', 1863),
            'España': ('ESP', 'Europe', 1909), 'Alemania': ('GER', 'Europe', 1900),
            'Portugal': ('POR', 'Europe', 1914), 'Países Bajos': ('NED', 'Europe', 1889),
            'Bélgica': ('BEL', 'Europe', 1895), 'México': ('MEX', 'North America', 1927),
            'Estados Unidos': ('USA', 'North America', 1913), 'Canadá': ('CAN', 'North America', 1912),
            'Uruguay': ('URU', 'South America', 1900), 'Colombia': ('COL', 'South America', 1924),
            'Japón': ('JPN', 'Asia', 1921), 'Corea del Sur': ('KOR', 'Asia', 1928),
            'Australia': ('AUS', 'Oceania', 1961), 'Marruecos': ('MAR', 'Africa', 1955),
            'Senegal': ('SEN', 'Africa', 1960), 'Nigeria': ('NGA', 'Africa', 1945),
            'Egipto': ('EGY', 'Africa', 1921), 'Costa de Marfil': ('CIV', 'Africa', 1960),
            'Ghana': ('GHA', 'Africa', 1957), 'Croacia': ('CRO', 'Europe', 1912),
            'Suiza': ('SUI', 'Europe', 1895), 'Suecia': ('SWE', 'Europe', 1904),
            'Noruega': ('NOR', 'Europe', 1902), 'Túnez': ('TUN', 'Africa', 1957),
            'Ecuador': ('ECU', 'South America', 1925), 'Paraguay': ('PAR', 'South America', 1906),
            'Irán': ('IRN', 'Asia', 1920), 'Arabia Saudita': ('KSA', 'Asia', 1956),
            'Austria': ('AUT', 'Europe', 1904), 'Turquía': ('TUR', 'Europe', 1923),
            'República Checa': ('CZE', 'Europe', 1901), 'Bosnia-Herzegovina': ('BIH', 'Europe', 1992),
            'Qatar': ('QAT', 'Asia', 1960), 'Curazao': ('CUW', 'North America', 1921),
            'Cabo Verde': ('CPV', 'Africa', 1982), 'Haití': ('HAI', 'North America', 1904),
            'Escocia': ('SCO', 'Europe', 1873), 'Irak': ('IRQ', 'Asia', 1948),
            'Jordania': ('JOR', 'Asia', 1949), 'Uzbekistán': ('UZB', 'Asia', 1946),
            'RD Congo': ('COD', 'Africa', 1919), 'Nueva Zelanda': ('NZL', 'Oceania', 1891),
            'Argelia': ('ALG', 'Africa', 1962), 'Panamá': ('PAN', 'North America', 1937),
        }

        comp = Competition(id=uuid.uuid4(), name='FIFA World Cup 2026', season='2026',
                           start_date=date(2026, 6, 11), end_date=date(2026, 7, 19),
                           competition_type='world_cup', format='group_plus_knockout')
        db.add(comp)
        db.flush()

        team_objects = {}
        for group_letter, team_names in OFFICIAL_GROUPS.items():
            for name in team_names:
                meta = TEAM_META.get(name, (None, 'Unknown', None))
                t = Team(name=name, fifa_code=meta[0], continent=meta[1], founded_year=meta[2], is_national_team=True)
                db.add(t)
                db.flush()
                db.add(EloRating(team_id=t.id, rating_date=date.today(), elo_score=1500 + (48 - len(team_objects)) * 20, rank=len(team_objects) + 1))
                db.add(FifaRanking(team_id=t.id, ranking_date=date.today(), rank=len(team_objects) + 1, previous_rank=len(team_objects) + 2, total_points=1800.0 - len(team_objects) * 15, confederation=meta[1]))
                db.add(XGMetrics(team_id=t.id, metric_date=date.today(), xg_for=2.5 - len(team_objects) * 0.04, xg_against=0.8 + len(team_objects) * 0.03, xg_diff=1.7 - len(team_objects) * 0.07))
                team_objects[name] = t

        groups = {}
        for group_letter, team_names in OFFICIAL_GROUPS.items():
            grp = Group(competition_id=comp.id, name=group_letter)
            db.add(grp)
            db.flush()
            groups[group_letter] = grp
            for pos, name in enumerate(team_names, 1):
                tm = team_objects[name]
                db.add(GroupStanding(group_id=grp.id, team_id=tm.id, position=pos, played=0, won=0, drawn=0, lost=0, goals_for=0, goals_against=0, goal_difference=0, points=0, qualified=False))

        match_date = datetime(2026, 6, 11, 12, 0)
        for group_letter, team_names in OFFICIAL_GROUPS.items():
            gt = [team_objects[n] for n in team_names]
            for i in range(len(gt)):
                for j in range(i + 1, len(gt)):
                    db.add(Match(competition_id=comp.id, home_team_id=gt[i].id, away_team_id=gt[j].id, match_date=match_date, stage='group_stage', group_name=group_letter))
                    match_date += timedelta(hours=4)
                    if match_date.hour >= 22:
                        match_date += timedelta(days=1)
                        match_date = match_date.replace(hour=10)

        db.commit()
        print(f'Seeded {len(team_objects)} teams across 12 groups (72 matches)')
finally:
    db.close()
"

# --- Numba warm-up ---
echo "Running Numba warm-up..."
python -c "
from app.core.warmup import warmup_numba; warmup_numba()
"

# --- Start application ---
echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --log-level info
