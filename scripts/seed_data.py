"""
Seed script — populates the database with FIFA 2026 groups and realistic initial data.
"""

import uuid
from datetime import date, datetime, timedelta

from app.db.session import SessionLocal
from app.models.competition import Competition
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.match import Match
from app.models.team import Team
from app.models.xg_metrics import XGMetrics


OFFICIAL_GROUPS = {
    "A": ["México", "Sudáfrica", "Corea del Sur", "República Checa"],
    "B": ["Canadá", "Bosnia-Herzegovina", "Qatar", "Suiza"],
    "C": ["Brasil", "Marruecos", "Haití", "Escocia"],
    "D": ["Estados Unidos", "Paraguay", "Australia", "Turquía"],
    "E": ["Alemania", "Curazao", "Costa de Marfil", "Ecuador"],
    "F": ["Países Bajos", "Japón", "Suecia", "Túnez"],
    "G": ["Bélgica", "Egipto", "Nigeria", "Nueva Zelanda"],
    "H": ["España", "Cabo Verde", "Arabia Saudita", "Uruguay"],
    "I": ["Francia", "Senegal", "Irak", "Noruega"],
    "J": ["Argentina", "Argelia", "Austria", "Jordania"],
    "K": ["Portugal", "RD Congo", "Uzbekistán", "Colombia"],
    "L": ["Inglaterra", "Croacia", "Ghana", "Panamá"],
}

TEAM_META = {
    "Argentina": ("ARG", "South America", 1900),
    "Brasil": ("BRA", "South America", 1914),
    "Francia": ("FRA", "Europe", 1904),
    "Inglaterra": ("ENG", "Europe", 1863),
    "España": ("ESP", "Europe", 1909),
    "Alemania": ("GER", "Europe", 1900),
    "Portugal": ("POR", "Europe", 1914),
    "Países Bajos": ("NED", "Europe", 1889),
    "Bélgica": ("BEL", "Europe", 1895),
    "México": ("MEX", "North America", 1927),
    "Estados Unidos": ("USA", "North America", 1913),
    "Canadá": ("CAN", "North America", 1912),
    "Uruguay": ("URU", "South America", 1900),
    "Colombia": ("COL", "South America", 1924),
    "Japón": ("JPN", "Asia", 1921),
    "Corea del Sur": ("KOR", "Asia", 1928),
    "Australia": ("AUS", "Oceania", 1961),
    "Marruecos": ("MAR", "Africa", 1955),
    "Senegal": ("SEN", "Africa", 1960),
    "Nigeria": ("NGA", "Africa", 1945),
    "Egipto": ("EGY", "Africa", 1921),
    "Costa de Marfil": ("CIV", "Africa", 1960),
    "Ghana": ("GHA", "Africa", 1957),
    "Croacia": ("CRO", "Europe", 1912),
    "Suiza": ("SUI", "Europe", 1895),
    "Suecia": ("SWE", "Europe", 1904),
    "Noruega": ("NOR", "Europe", 1902),
    "Túnez": ("TUN", "Africa", 1957),
    "Ecuador": ("ECU", "South America", 1925),
    "Paraguay": ("PAR", "South America", 1906),
    "Irán": ("IRN", "Asia", 1920),
    "Arabia Saudita": ("KSA", "Asia", 1956),
    "Austria": ("AUT", "Europe", 1904),
    "Turquía": ("TUR", "Europe", 1923),
    "República Checa": ("CZE", "Europe", 1901),
    "Bosnia-Herzegovina": ("BIH", "Europe", 1992),
    "Qatar": ("QAT", "Asia", 1960),
    "Curazao": ("CUW", "North America", 1921),
    "Cabo Verde": ("CPV", "Africa", 1982),
    "Haití": ("HAI", "North America", 1904),
    "Escocia": ("SCO", "Europe", 1873),
    "Irak": ("IRQ", "Asia", 1948),
    "Jordania": ("JOR", "Asia", 1949),
    "Uzbekistán": ("UZB", "Asia", 1946),
    "RD Congo": ("COD", "Africa", 1919),
    "Nueva Zelanda": ("NZL", "Oceania", 1891),
    "Argelia": ("ALG", "Africa", 1962),
    "Panamá": ("PAN", "North America", 1937),
    "Sudáfrica": ("RSA", "Africa", 1992),
}

# Realistic team strengths (Elo, FIFA rank, FIFA points, xG for, xG against)
TEAM_STRENGTH = {
    "Argentina": (2084, 1, 2110, 2.3, 0.6),
    "Brasil": (2070, 2, 2070, 2.4, 0.6),
    "Francia": (2065, 3, 2040, 2.2, 0.7),
    "Inglaterra": (2055, 4, 2010, 2.1, 0.7),
    "España": (2048, 5, 1990, 2.2, 0.8),
    "Alemania": (2035, 6, 1960, 2.0, 0.8),
    "Portugal": (2028, 7, 1940, 2.0, 0.8),
    "Países Bajos": (2020, 8, 1920, 2.0, 0.8),
    "Bélgica": (2010, 9, 1900, 2.0, 0.9),
    "Croacia": (1980, 10, 1870, 1.8, 0.9),
    "Uruguay": (1970, 11, 1850, 1.7, 0.9),
    "Colombia": (1960, 12, 1830, 1.7, 0.9),
    "Japón": (1950, 13, 1810, 1.6, 1.0),
    "Corea del Sur": (1940, 14, 1790, 1.6, 1.0),
    "Marruecos": (1930, 15, 1770, 1.5, 1.0),
    "Senegal": (1920, 16, 1750, 1.5, 1.0),
    "Suiza": (1910, 17, 1730, 1.5, 1.1),
    "Estados Unidos": (1900, 18, 1710, 1.5, 1.1),
    "México": (1890, 19, 1690, 1.5, 1.1),
    "Nigeria": (1880, 20, 1670, 1.5, 1.1),
    "Costa de Marfil": (1870, 21, 1650, 1.4, 1.1),
    "Ghana": (1860, 22, 1630, 1.4, 1.2),
    "Egipto": (1850, 23, 1610, 1.4, 1.2),
    "Túnez": (1840, 24, 1590, 1.4, 1.2),
    "Ecuador": (1830, 25, 1570, 1.3, 1.2),
    "Paraguay": (1820, 26, 1550, 1.3, 1.3),
    "Arabia Saudita": (1810, 27, 1530, 1.3, 1.3),
    "Australia": (1800, 28, 1510, 1.3, 1.3),
    "Argelia": (1790, 29, 1490, 1.3, 1.3),
    "Noruega": (1780, 30, 1470, 1.3, 1.3),
    "Suecia": (1770, 31, 1450, 1.2, 1.4),
    "Turquía": (1760, 32, 1430, 1.2, 1.4),
    "Escocia": (1750, 33, 1410, 1.2, 1.4),
    "Austria": (1740, 34, 1390, 1.2, 1.4),
    "República Checa": (1730, 35, 1370, 1.2, 1.5),
    "Irán": (1720, 36, 1350, 1.1, 1.5),
    "Sudáfrica": (1710, 37, 1330, 1.1, 1.5),
    "Canadá": (1700, 38, 1310, 1.1, 1.5),
    "Panamá": (1690, 39, 1290, 1.1, 1.5),
    "Bosnia-Herzegovina": (1680, 40, 1270, 1.0, 1.6),
    "Qatar": (1670, 41, 1250, 1.0, 1.6),
    "Cabo Verde": (1660, 42, 1230, 1.0, 1.6),
    "Haití": (1650, 43, 1210, 1.0, 1.6),
    "Irak": (1640, 44, 1190, 1.0, 1.7),
    "Jordania": (1630, 45, 1170, 0.9, 1.7),
    "Uzbekistán": (1620, 46, 1150, 0.9, 1.7),
    "RD Congo": (1610, 47, 1130, 0.9, 1.7),
    "Nueva Zelanda": (1600, 48, 1110, 0.9, 1.8),
    "Curazao": (1550, 49, 1050, 0.8, 1.8),
}


def seed():
    db = SessionLocal()

    competition = Competition(
        id=uuid.uuid4(),
        name="FIFA World Cup 2026",
        season="2026",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 19),
        competition_type="world_cup",
        format="group_plus_knockout",
    )
    db.add(competition)
    db.flush()

    team_objects = {}
    teams_bulk, elos_bulk, fifas_bulk, xgs_bulk = [], [], [], []

    for group_letter, team_names in OFFICIAL_GROUPS.items():
        for name in team_names:
            meta = TEAM_META.get(name, (None, "Unknown", None))
            fifa_code, continent, founded = meta
            strength = TEAM_STRENGTH.get(name, (1500, 100, 1000, 1.0, 1.5))
            elo_score, fifa_rank, fifa_points, xg_for, xg_against = strength

            team = Team(
                name=name,
                fifa_code=fifa_code,
                continent=continent,
                founded_year=founded,
                is_national_team=True,
            )
            db.add(team)
            db.flush()

            elo = EloRating(
                team_id=team.id,
                rating_date=date.today(),
                elo_score=elo_score,
                rank=fifa_rank,
            )
            db.add(elo)

            fifa = FifaRanking(
                team_id=team.id,
                ranking_date=date.today(),
                rank=fifa_rank,
                previous_rank=fifa_rank + 1,
                total_points=fifa_points,
                confederation=continent,
            )
            db.add(fifa)

            xg = XGMetrics(
                team_id=team.id,
                metric_date=date.today(),
                xg_for=xg_for,
                xg_against=xg_against,
                xg_diff=round(xg_for - xg_against, 2),
            )
            db.add(xg)

            team_objects[name] = team

    groups = {}
    for group_letter, team_names in OFFICIAL_GROUPS.items():
        group = Group(
            competition_id=competition.id,
            name=group_letter,
        )
        db.add(group)
        db.flush()
        groups[group_letter] = group

        for pos, name in enumerate(team_names, 1):
            team = team_objects[name]
            standing = GroupStanding(
                group_id=group.id,
                team_id=team.id,
                position=pos,
                played=0, won=0, drawn=0, lost=0,
                goals_for=0, goals_against=0, goal_difference=0,
                points=0, qualified=False,
            )
            db.add(standing)

    group_names = list(OFFICIAL_GROUPS.keys())
    match_date = datetime(2026, 6, 11, 12, 0)
    matches_bulk = []

    for group_letter in group_names:
        gt = [team_objects[n] for n in OFFICIAL_GROUPS[group_letter]]
        for i in range(len(gt)):
            for j in range(i + 1, len(gt)):
                matches_bulk.append(Match(
                    competition_id=competition.id,
                    home_team_id=gt[i].id,
                    away_team_id=gt[j].id,
                    match_date=match_date,
                    stage="group_stage",
                    group_name=group_letter,
                ))
                match_date += timedelta(hours=4)
                if match_date.hour >= 22:
                    match_date += timedelta(days=1)
                    match_date = match_date.replace(hour=10)

    db.bulk_save_objects(matches_bulk)
    db.commit()
    db.close()

    total = len(team_objects)
    total_matches = total // 4 * 6
    print(f"Seeded {total} teams across 12 groups ({total_matches} group matches)")


if __name__ == "__main__":
    seed()
