import uuid

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.cache_decorator import cached
from app.core.dependencies import get_db
from app.engine.match_prediction import MatchPredictionConfig, MatchPredictionEngine
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.simulation import Simulation, SimulationResult
from app.models.team import Team
from app.models.xg_metrics import XGMetrics
from app.services.calibration_service import CalibrationService

router = APIRouter(prefix="/comparison", tags=["Comparison"])


def _load_team_data(db: Session, team_id: uuid.UUID) -> dict:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    latest_elo = (
        db.query(EloRating)
        .filter(EloRating.team_id == team_id)
        .order_by(EloRating.rating_date.desc())
        .first()
    )
    elo_score = latest_elo.elo_score if latest_elo else 1500

    latest_xg = (
        db.query(XGMetrics)
        .filter(XGMetrics.team_id == team_id)
        .order_by(XGMetrics.metric_date.desc())
        .first()
    )

    latest_fifa = (
        db.query(FifaRanking)
        .filter(FifaRanking.team_id == team_id)
        .order_by(FifaRanking.ranking_date.desc())
        .first()
    )

    igf_val = round(min(100, max(0, (elo_score - 1300) / 8)), 2)

    standing = (
        db.query(GroupStanding)
        .options(joinedload(GroupStanding.group))
        .filter(GroupStanding.team_id == team_id)
        .first()
    )

    return {
        "team_id": str(team.id),
        "team_name": team.name,
        "fifa_code": team.fifa_code,
        "continent": team.continent,
        "flag_url": team.flag_url,
        "elo_score": elo_score,
        "igf_score": igf_val,
        "fifa_rank": latest_fifa.rank if latest_fifa else None,
        "xg_for": latest_xg.xg_for if latest_xg else None,
        "xg_against": latest_xg.xg_against if latest_xg else None,
        "group_name": standing.group.name if standing and standing.group else None,
        "group_position": standing.position if standing else None,
        "group_points": standing.points if standing else None,
    }


def _get_simulation_data(db: Session, team_id: uuid.UUID) -> dict | None:
    latest_sim = (
        db.query(Simulation)
        .filter(Simulation.status == "completed")
        .order_by(Simulation.completed_at.desc())
        .first()
    )
    if not latest_sim:
        return None

    result = (
        db.query(SimulationResult)
        .filter(
            SimulationResult.simulation_id == latest_sim.id,
            SimulationResult.team_id == team_id,
        )
        .first()
    )
    if not result:
        return None

    n = max(latest_sim.num_simulations, 1)
    return {
        "win_prob": round(result.won_tournament / n * 100, 1),
        "final_prob": round(result.reached_final / n * 100, 1),
        "sf_prob": round(result.reached_semi_final / n * 100, 1),
        "qf_prob": round(result.reached_quarter_final / n * 100, 1),
        "r16_prob": round(result.reached_round_of_16 / n * 100, 1),
        "r32_prob": round(result.reached_round_of_32 / n * 100, 1),
        "avg_points": round(float(result.points), 2),
    }


@router.get("/teams/{team_a_id}/{team_b_id}")
@cached("comparison:teams")
def compare_teams(team_a_id: uuid.UUID, team_b_id: uuid.UUID, db: Session = Depends(get_db)):
    team_a = _load_team_data(db, team_a_id)
    team_b = _load_team_data(db, team_b_id)

    sim_a = _get_simulation_data(db, team_a_id)
    sim_b = _get_simulation_data(db, team_b_id)

    prediction = None
    if team_a.get("group_name") and team_a["group_name"] == team_b.get("group_name"):
        from app.domain.entities import TeamEntity

        cal_config = CalibrationService.build_config_with_adjustments()
        engine = MatchPredictionEngine(config=cal_config)

        home_entity = TeamEntity(
            id=team_a_id,
            name=team_a["team_name"],
            fifa_code=team_a.get("fifa_code"),
            continent=team_a.get("continent"),
            elo_score=team_a["elo_score"],
            igf_score=team_a["igf_score"],
        )
        away_entity = TeamEntity(
            id=team_b_id,
            name=team_b["team_name"],
            fifa_code=team_b.get("fifa_code"),
            continent=team_b.get("continent"),
            elo_score=team_b["elo_score"],
            igf_score=team_b["igf_score"],
        )

        result = engine.predict_full(home_entity, away_entity, home_advantage=True)
        prediction = {
            "home_win_prob": result.home_win_prob,
            "draw_prob": result.draw_prob,
            "away_win_prob": result.away_win_prob,
            "home_expected_goals": result.home_expected_goals,
            "away_expected_goals": result.away_expected_goals,
            "most_likely_score": result.most_likely_score,
            "confidence_index": result.confidence_index,
            "confidence_level": result.confidence_level,
            "surprise_risk": result.surprise_risk,
            "btts_prob": result.btts_prob,
            "over_25_prob": result.over_25_prob,
        }

    return {
        "team_a": {**team_a, "simulation": sim_a},
        "team_b": {**team_b, "simulation": sim_b},
        "head_to_head_prediction": prediction,
    }
