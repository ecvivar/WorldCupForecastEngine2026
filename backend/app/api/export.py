import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.cache_decorator import cached
from app.core.dependencies import get_db
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.match import Match
from app.models.simulation import Simulation, SimulationResult
from app.models.team import Team
from app.services.match_service import MatchService
from app.services.ranking_service import RankingService
from app.services.team_service import TeamService

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/team/{team_id}")
@cached("export:team")
def export_team_json(team_id: uuid.UUID, db: Session = Depends(get_db)):
    service = TeamService(db)
    team = service.get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    latest_elo = (
        db.query(EloRating)
        .filter(EloRating.team_id == team_id)
        .order_by(EloRating.rating_date.desc())
        .first()
    )
    latest_fifa = (
        db.query(FifaRanking)
        .filter(FifaRanking.team_id == team_id)
        .order_by(FifaRanking.ranking_date.desc())
        .first()
    )
    elo_score = latest_elo.elo_score if latest_elo else 1500
    igf_val = round(min(100, max(0, (elo_score - 1300) / 8)), 2)

    standing = (
        db.query(GroupStanding)
        .options(joinedload(GroupStanding.group))
        .filter(GroupStanding.team_id == team_id)
        .first()
    )

    matches = (
        db.query(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .filter((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        .order_by(Match.match_date)
        .all()
    )

    return {
        "team": {
            "id": str(team.id),
            "name": team.name,
            "fifa_code": team.fifa_code,
            "continent": team.continent,
            "flag_url": team.flag_url,
            "founded_year": team.founded_year,
            "is_national_team": team.is_national_team,
        },
        "ratings": {
            "elo_score": elo_score,
            "igf_score": igf_val,
            "fifa_rank": latest_fifa.rank if latest_fifa else None,
        },
        "group": {
            "name": standing.group.name if standing and standing.group else None,
            "position": standing.position if standing else None,
            "points": standing.points if standing else None,
        } if standing else None,
        "matches": [
            {
                "id": str(m.id),
                "date": m.match_date.isoformat() if m.match_date else None,
                "stage": m.stage,
                "opponent": m.away_team.name if m.home_team_id == team_id else m.home_team.name,
                "home_or_away": "home" if m.home_team_id == team_id else "away",
                "goals_for": m.home_goals if m.home_team_id == team_id else m.away_goals,
                "goals_against": m.away_goals if m.home_team_id == team_id else m.home_goals,
                "status": m.status,
            }
            for m in matches
        ],
    }


@router.get("/match/{match_id}")
@cached("export:match")
def export_match_json(match_id: uuid.UUID, db: Session = Depends(get_db)):
    service = MatchService(db)
    match = service.get_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    prediction = service.get_full_prediction(match_id)

    return {
        "match": {
            "id": str(match.id),
            "date": match.match_date.isoformat() if match.match_date else None,
            "stage": match.stage,
            "group_name": match.group_name,
            "status": match.status,
            "home_team": match.home_team.name if match.home_team else None,
            "away_team": match.away_team.name if match.away_team else None,
            "home_goals": match.home_goals,
            "away_goals": match.away_goals,
            "is_neutral_venue": match.is_neutral_venue,
        },
        "prediction": prediction,
    }


@router.get("/simulation/{sim_id}")
@cached("export:simulation")
def export_simulation_json(sim_id: uuid.UUID, db: Session = Depends(get_db)):
    sim = (
        db.query(Simulation)
        .options(joinedload(Simulation.results).joinedload(SimulationResult.team))
        .filter(Simulation.id == sim_id)
        .first()
    )
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    n = max(sim.num_simulations, 1)
    return {
        "simulation": {
            "id": str(sim.id),
            "name": sim.name,
            "num_simulations": sim.num_simulations,
            "status": sim.status,
            "created_at": sim.created_at.isoformat() if sim.created_at else None,
            "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
        },
        "results": [
            {
                "team_name": r.team.name if r.team else "Unknown",
                "fifa_code": r.team.fifa_code if r.team else None,
                "group_name": r.group_name,
                "win_prob": round(r.won_tournament / n * 100, 1),
                "final_prob": round(r.reached_final / n * 100, 1),
                "sf_prob": round(r.reached_semi_final / n * 100, 1),
                "qf_prob": round(r.reached_quarter_final / n * 100, 1),
                "r16_prob": round(r.reached_round_of_16 / n * 100, 1),
                "r32_prob": round(r.reached_round_of_32 / n * 100, 1),
            }
            for r in sorted(sim.results, key=lambda x: x.won_tournament, reverse=True)
        ],
    }


@router.get("/group/{group_id}")
@cached("export:group")
def export_group_json(group_id: uuid.UUID, db: Session = Depends(get_db)):
    group = (
        db.query(Group)
        .options(joinedload(Group.standings).joinedload(GroupStanding.team))
        .filter(Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return {
        "group": {
            "id": str(group.id),
            "name": group.name,
            "stage": group.stage,
        },
        "standings": [
            {
                "position": s.position,
                "team_name": s.team.name if s.team else "?",
                "fifa_code": s.team.fifa_code if s.team else None,
                "played": s.played,
                "won": s.won,
                "drawn": s.drawn,
                "lost": s.lost,
                "goals_for": s.goals_for,
                "goals_against": s.goals_against,
                "goal_difference": s.goal_difference,
                "points": s.points,
                "qualified": s.qualified,
            }
            for s in sorted(group.standings, key=lambda x: x.position)
        ],
    }


@router.get("/rankings")
@cached("export:rankings")
def export_rankings_json(db: Session = Depends(get_db)):
    ranking_service = RankingService(db)
    elo = ranking_service.get_latest_elo(limit=100)
    fifa = ranking_service.get_latest_fifa(limit=100)
    igf = ranking_service.compute_igf()
    return {
        "elo": [
            {"rank": i + 1, "team_name": r.get("team_name"), "elo_score": r.get("elo_score")}
            for i, r in enumerate(elo)
        ],
        "fifa": [
            {"rank": r.get("rank"), "team_name": r.get("team_name"), "total_points": r.get("total_points")}
            for r in fifa
        ],
        "igf": [
            {"team_name": s.team_name, "igf_score": s.igf_score, "components": s.components}
            for s in igf
        ],
    }


@router.get("/matches/csv")
def export_matches_csv(db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.match_date)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "date", "stage", "group", "home_team", "away_team", "home_goals", "away_goals", "status"])
    for m in matches:
        writer.writerow([
            str(m.id),
            m.match_date.isoformat() if m.match_date else "",
            m.stage,
            m.group_name or "",
            m.home_team.name if m.home_team else "",
            m.away_team.name if m.away_team else "",
            m.home_goals if m.home_goals is not None else "",
            m.away_goals if m.away_goals is not None else "",
            m.status,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=matches.csv"},
    )


@router.get("/simulations/csv")
def export_simulations_csv(db: Session = Depends(get_db)):
    results = (
        db.query(SimulationResult)
        .options(joinedload(SimulationResult.team), joinedload(SimulationResult.simulation))
        .order_by(SimulationResult.won_tournament.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "simulation_id", "simulation_name", "team_name", "fifa_code",
        "group_name", "win_prob_pct", "final_prob_pct", "sf_prob_pct",
        "qf_prob_pct", "r16_prob_pct", "r32_prob_pct", "avg_points",
    ])
    for r in results:
        n = max(r.simulation.num_simulations, 1) if r.simulation else 1
        writer.writerow([
            str(r.simulation_id),
            r.simulation.name if r.simulation else "",
            r.team.name if r.team else "",
            r.team.fifa_code if r.team else "",
            r.group_name or "",
            round(r.won_tournament / n * 100, 1),
            round(r.reached_final / n * 100, 1),
            round(r.reached_semi_final / n * 100, 1),
            round(r.reached_quarter_final / n * 100, 1),
            round(r.reached_round_of_16 / n * 100, 1),
            round(r.reached_round_of_32 / n * 100, 1),
            round(float(r.points), 2),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=simulations.csv"},
    )
