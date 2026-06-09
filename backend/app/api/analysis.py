import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.cache_decorator import cached
from app.core.dependencies import get_db
from app.engine.igf import IGFEngine
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.models.match import Match
from app.models.team import Team
from app.models.xg_metrics import XGMetrics
from app.services.match_service import MatchService

router = APIRouter(tags=["Analysis"])


@router.get("/groups/{group_id}/analysis")
@cached("analysis:group")
def analyze_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    group = (
        db.query(Group)
        .options(joinedload(Group.standings).joinedload(GroupStanding.team))
        .filter(Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    standings = sorted(group.standings, key=lambda s: s.position) if group.standings else []
    teams_data = []
    igf_scores = []

    for s in standings:
        if not s.team:
            continue
        latest_elo = (
            db.query(EloRating)
            .filter(EloRating.team_id == s.team_id)
            .order_by(EloRating.rating_date.desc())
            .first()
        )
        elo_score = latest_elo.elo_score if latest_elo else 1500
        igf_val = min(100, max(0, (elo_score - 1300) / 8))
        igf_scores.append(igf_val)

        teams_data.append({
            "team_name": s.team.name,
            "fifa_code": s.team.fifa_code,
            "continent": s.team.continent,
            "position": s.position,
            "elo_score": elo_score,
            "igf_score": round(igf_val, 2),
        })

    strength_range = round(max(igf_scores) - min(igf_scores), 2) if igf_scores else 0
    competitiveness = round(100 - strength_range * 2, 2) if strength_range < 50 else 0

    return {
        "group_name": group.name,
        "teams": teams_data,
        "competitiveness_index": max(0, min(100, competitiveness)),
        "strength_range": strength_range,
        "favorite": teams_data[0]["team_name"] if teams_data else None,
        "outsider": teams_data[-1]["team_name"] if teams_data else None,
    }


@router.get("/rankings/power-ranking")
@cached("analysis:power-ranking")
def power_ranking(db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    rows = []
    for team in teams:
        latest_elo = (
            db.query(EloRating)
            .filter(EloRating.team_id == team.id)
            .order_by(EloRating.rating_date.desc())
            .first()
        )
        latest_fifa = (
            db.query(FifaRanking)
            .filter(FifaRanking.team_id == team.id)
            .order_by(FifaRanking.ranking_date.desc())
            .first()
        )
        elo_score = latest_elo.elo_score if latest_elo else 1500
        fifa_rank = latest_fifa.rank if latest_fifa else 100
        igf_val = min(100, max(0, (elo_score - 1300) / 8))

        rows.append({
            "team_name": team.name,
            "fifa_code": team.fifa_code,
            "continent": team.continent,
            "elo_score": elo_score,
            "fifa_rank": fifa_rank,
            "igf_score": round(igf_val, 2),
        })

    rows.sort(key=lambda r: r["igf_score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    return {
        "title_contenders": [r for r in rows[:10]],
        "semi_final_candidates": [r for r in rows[:10]],
        "quarter_final_candidates": [r for r in rows[:20]],
        "early_exit_candidates": [r for r in rows[-10:]],
    }


@router.get("/predictions/full/{match_id}")
@cached("analysis:full-prediction")
def full_prediction(match_id: uuid.UUID, db: Session = Depends(get_db)):
    service = MatchService(db)
    result = service.get_full_prediction(match_id)
    if not result:
        raise HTTPException(status_code=404, detail="Match not found")
    return result


@router.get("/matches/calendar")
@cached("analysis:calendar")
def match_calendar(db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.match_date)
        .all()
    )

    service = MatchService(db)
    calendar = []
    for m in matches:
        pred = service.get_full_prediction(m.id)
        calendar.append({
            "match_id": str(m.id),
            "stage": m.stage,
            "group_name": m.group_name,
            "match_date": m.match_date.isoformat(),
            "home_team": m.home_team.name if m.home_team else "?",
            "away_team": m.away_team.name if m.away_team else "?",
            "most_likely_score": pred["most_likely_score"] if pred else None,
            "home_win_prob": pred["home_win_prob"] if pred else None,
            "draw_prob": pred["draw_prob"] if pred else None,
            "away_win_prob": pred["away_win_prob"] if pred else None,
            "confidence_index": pred["confidence_index"] if pred else None,
            "confidence_level": pred["confidence_level"] if pred else None,
            "surprise_risk": pred["surprise_risk"] if pred else None,
        })

    return calendar


@router.get("/predictions/betting/{match_id}")
@cached("analysis:betting")
def betting_markets(match_id: uuid.UUID, db: Session = Depends(get_db)):
    service = MatchService(db)
    pred = service.get_full_prediction(match_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        "match_id": pred["match_id"],
        "home_team": pred["home_team"],
        "away_team": pred["away_team"],
        "1": pred["home_win_prob"],
        "X": pred["draw_prob"],
        "2": pred["away_win_prob"],
        "btts_yes": pred["btts_prob"],
        "btts_no": round(1.0 - pred["btts_prob"], 4),
        "over_2_5": pred["over_25_prob"],
        "under_2_5": pred["under_25_prob"],
        "over_3_5": pred["over_35_prob"],
        "home_clean_sheet": pred["home_clean_sheet"],
        "away_clean_sheet": pred["away_clean_sheet"],
    }
