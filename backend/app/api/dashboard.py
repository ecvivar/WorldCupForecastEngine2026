import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.cache_decorator import cached
from app.core.dependencies import get_db
from app.models.elo_rating import EloRating
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.match import Match
from app.models.simulation import Simulation, SimulationResult
from app.models.team import Team
from app.services.match_service import MatchService

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
@cached("dashboard:main")
def dashboard(db: Session = Depends(get_db)):
    total_teams = db.query(Team).count()
    total_matches = db.query(Match).count()
    total_groups = db.query(Group).count()

    group_matches = db.query(Match).filter(Match.stage == "group_stage").count()
    knockout_matches = total_matches - group_matches

    teams = db.query(Team).all()
    top_teams = []
    for team in teams:
        latest_elo = (
            db.query(EloRating)
            .filter(EloRating.team_id == team.id)
            .order_by(EloRating.rating_date.desc())
            .first()
        )
        elo_score = latest_elo.elo_score if latest_elo else 1500
        igf_val = round(min(100, max(0, (elo_score - 1300) / 8)), 2)
        top_teams.append({
            "team_name": team.name,
            "fifa_code": team.fifa_code,
            "continent": team.continent,
            "igf_score": igf_val,
            "elo_score": elo_score,
        })
    top_teams.sort(key=lambda r: r["igf_score"], reverse=True)
    for i, t in enumerate(top_teams, 1):
        t["rank"] = i

    latest_sim = (
        db.query(Simulation)
        .options(joinedload(Simulation.results).joinedload(SimulationResult.team))
        .filter(Simulation.status == "completed")
        .order_by(Simulation.completed_at.desc())
        .first()
    )
    simulation_summary = None
    winner_probs = []
    if latest_sim:
        n = max(latest_sim.num_simulations, 1)
        results_sorted = sorted(latest_sim.results, key=lambda r: r.won_tournament, reverse=True)
        winner_probs = [
            {
                "team_name": r.team.name if r.team else "Unknown",
                "fifa_code": r.team.fifa_code if r.team else None,
                "win_prob": round(r.won_tournament / n * 100, 1),
                "final_prob": round(r.reached_final / n * 100, 1),
                "sf_prob": round(r.reached_semi_final / n * 100, 1),
                "qf_prob": round(r.reached_quarter_final / n * 100, 1),
            }
            for r in results_sorted[:10]
        ]
        simulation_summary = {
            "id": str(latest_sim.id),
            "name": latest_sim.name,
            "num_simulations": latest_sim.num_simulations,
            "completed_at": latest_sim.completed_at.isoformat() if latest_sim.completed_at else None,
        }

    service = MatchService(db)
    matches = (
        db.query(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.match_date)
        .limit(10)
        .all()
    )
    recent_predictions = []
    for m in matches:
        pred = service.get_full_prediction(m.id)
        if pred:
            recent_predictions.append({
                "match_id": str(m.id),
                "stage": m.stage,
                "match_date": m.match_date.isoformat() if m.match_date else None,
                "home_team": m.home_team.name if m.home_team else "?",
                "away_team": m.away_team.name if m.away_team else "?",
                "home_win_prob": pred["home_win_prob"],
                "draw_prob": pred["draw_prob"],
                "away_win_prob": pred["away_win_prob"],
                "most_likely_score": pred["most_likely_score"],
                "confidence_index": pred["confidence_index"],
                "confidence_level": pred["confidence_level"],
                "surprise_risk": pred["surprise_risk"],
            })

    groups_data = []
    all_groups = db.query(Group).options(
        joinedload(Group.standings).joinedload(GroupStanding.team)
    ).order_by(Group.name).all()
    for g in all_groups:
        standings = sorted(g.standings, key=lambda s: s.position) if g.standings else []
        groups_data.append({
            "name": g.name,
            "teams": [
                {
                    "team_name": s.team.name if s.team else "?",
                    "fifa_code": s.team.fifa_code if s.team else None,
                    "position": s.position,
                    "points": s.points,
                    "goal_difference": s.goal_difference,
                    "qualified": s.qualified,
                }
                for s in standings[:4]
            ],
        })

    return {
        "total_teams": total_teams,
        "total_matches": total_matches,
        "total_groups": total_groups,
        "group_matches": group_matches,
        "knockout_matches": knockout_matches,
        "top_teams": top_teams[:10],
        "simulation": simulation_summary,
        "winner_probs": winner_probs,
        "recent_predictions": recent_predictions,
        "groups": groups_data,
    }


@router.get("/simulations/{sim_id}/probabilities")
def simulation_probabilities(sim_id: uuid.UUID, db: Session = Depends(get_db)):
    sim = (
        db.query(Simulation)
        .options(joinedload(Simulation.results).joinedload(SimulationResult.team))
        .filter(Simulation.id == sim_id)
        .first()
    )
    if not sim:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Simulation not found")

    n = max(sim.num_simulations, 1)
    teams_probs = []
    for r in sim.results:
        team_name = r.team.name if r.team else "Unknown"
        fifa_code = r.team.fifa_code if r.team else None
        continent = r.team.continent if r.team else None
        teams_probs.append({
            "team_name": team_name,
            "fifa_code": fifa_code,
            "continent": continent,
            "group_name": r.group_name,
            "group_position": r.group_position,
            "qualify_r32_prob": round(r.reached_round_of_32 / n * 100, 1),
            "r16_prob": round(r.reached_round_of_16 / n * 100, 1),
            "qf_prob": round(r.reached_quarter_final / n * 100, 1),
            "sf_prob": round(r.reached_semi_final / n * 100, 1),
            "final_prob": round(r.reached_final / n * 100, 1),
            "win_prob": round(r.won_tournament / n * 100, 1),
            "avg_points": round(float(r.points), 2),
        })

    teams_probs.sort(key=lambda r: r["win_prob"], reverse=True)

    groups_probs = {}
    for r in sim.results:
        gn = r.group_name or "?"
        if gn not in groups_probs:
            groups_probs[gn] = []
        team_name = r.team.name if r.team else "Unknown"
        groups_probs[gn].append({
            "team_name": team_name,
            "fifa_code": r.team.fifa_code if r.team else None,
            "qualify_r32_prob": round(r.reached_round_of_32 / n * 100, 1),
            "avg_points": round(float(r.points), 2),
        })

    return {
        "simulation_id": str(sim.id),
        "num_simulations": sim.num_simulations,
        "teams": teams_probs,
        "groups": dict(sorted(groups_probs.items())),
    }
