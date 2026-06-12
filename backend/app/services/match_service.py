import uuid

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.domain.entities import TeamEntity
from app.engine.igf import IGFEngine
from app.engine.match_prediction import MatchPredictionConfig, MatchPredictionEngine
from app.models.elo_rating import EloRating
from app.models.fifa_ranking import FifaRanking
from app.models.match import Match
from app.models.team import Team
from app.models.xg_metrics import XGMetrics
from app.schemas.match import MatchCreate, MatchPrediction
from app.services.calibration_service import CalibrationService


class MatchService:
    def __init__(self, db: Session):
        self.db = db
        self.igf_engine = IGFEngine()
        self._all_igf_scores: dict[str, dict] | None = None
        cal_config = CalibrationService.build_config_with_adjustments()
        self.prediction_engine = MatchPredictionEngine(config=cal_config)

    def get_all(
        self, skip: int = 0, limit: int = 20, stage: str | None = None
    ) -> list[Match]:
        query = self.db.query(Match).options(
            joinedload(Match.home_team), joinedload(Match.away_team)
        )
        if stage:
            query = query.filter(Match.stage == stage)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, match_id: uuid.UUID) -> Match | None:
        return (
            self.db.query(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .filter(Match.id == match_id)
            .first()
        )

    def create(self, data: MatchCreate) -> Match:
        match = Match(**data.model_dump())
        self.db.add(match)
        self.db.commit()
        self.db.refresh(match)
        return match

    def _compute_all_igf_scores(self) -> dict[str, dict]:
        if self._all_igf_scores is not None:
            return self._all_igf_scores

        teams = self.db.query(Team).all()
        rows = []
        for team in teams:
            latest_elo = (
                self.db.query(EloRating)
                .filter(EloRating.team_id == team.id)
                .order_by(EloRating.rating_date.desc())
                .first()
            )
            latest_fifa = (
                self.db.query(FifaRanking)
                .filter(FifaRanking.team_id == team.id)
                .order_by(FifaRanking.ranking_date.desc())
                .first()
            )
            latest_xg = (
                self.db.query(XGMetrics)
                .filter(XGMetrics.team_id == team.id)
                .order_by(XGMetrics.metric_date.desc())
                .first()
            )
            rows.append({
                "team_name": team.name,
                "elo_score": latest_elo.elo_score if latest_elo else 1500,
                "fifa_rank": latest_fifa.rank if latest_fifa else 100,
                "xg_for": latest_xg.xg_for if latest_xg else 1.0,
                "xg_against": latest_xg.xg_against if latest_xg else 1.0,
            })

        df = pd.DataFrame(rows)
        self._all_igf_scores = self.igf_engine.compute_team_scores(df)
        return self._all_igf_scores

    def _load_team_entity(self, team: Team) -> TeamEntity:
        all_igf = self._compute_all_igf_scores()
        igf_info = all_igf.get(team.name, {"igf_score": 50.0, "components": {}})

        latest_elo = (
            self.db.query(EloRating)
            .filter(EloRating.team_id == team.id)
            .order_by(EloRating.rating_date.desc())
            .first()
        )
        elo_score = latest_elo.elo_score if latest_elo else 1500

        return TeamEntity(
            id=team.id,
            name=team.name,
            fifa_code=team.fifa_code,
            continent=team.continent,
            elo_score=elo_score,
            igf_score=igf_info.get("igf_score", 50.0),
        )

    def get_predictions(self, match_id: uuid.UUID) -> MatchPrediction | None:
        match = self.get_by_id(match_id)
        if not match or not match.home_team or not match.away_team:
            return None

        home_entity = self._load_team_entity(match.home_team)
        away_entity = self._load_team_entity(match.away_team)

        result = self.prediction_engine.predict_full(
            home_entity, away_entity,
            home_advantage=not match.is_neutral_venue,
        )
        return MatchPrediction(
            match_id=match_id,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            home_win_prob=result.home_win_prob,
            draw_prob=result.draw_prob,
            away_win_prob=result.away_win_prob,
            home_expected_goals=result.home_expected_goals,
            away_expected_goals=result.away_expected_goals,
            most_likely_score=result.most_likely_score,
        )

    def get_full_prediction(self, match_id: uuid.UUID) -> dict | None:
        match = self.get_by_id(match_id)
        if not match or not match.home_team or not match.away_team:
            return None

        home_entity = self._load_team_entity(match.home_team)
        away_entity = self._load_team_entity(match.away_team)

        result = self.prediction_engine.predict_full(
            home_entity, away_entity,
            home_advantage=not match.is_neutral_venue,
        )
        return {
            "match_id": str(match_id),
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "home_win_prob": result.home_win_prob,
            "draw_prob": result.draw_prob,
            "away_win_prob": result.away_win_prob,
            "home_expected_goals": result.home_expected_goals,
            "away_expected_goals": result.away_expected_goals,
            "most_likely_score": result.most_likely_score,
            "top_10_scores": result.top_10_scores,
            "confidence_index": result.confidence_index,
            "confidence_level": result.confidence_level,
            "surprise_risk": result.surprise_risk,
            "btts_prob": result.btts_prob,
            "over_25_prob": result.over_25_prob,
            "under_25_prob": result.under_25_prob,
            "over_35_prob": result.over_35_prob,
            "home_clean_sheet": result.home_clean_sheet,
            "away_clean_sheet": result.away_clean_sheet,
        }

    def count(self, stage: str | None = None) -> int:
        query = self.db.query(Match)
        if stage:
            query = query.filter(Match.stage == stage)
        return query.count()
