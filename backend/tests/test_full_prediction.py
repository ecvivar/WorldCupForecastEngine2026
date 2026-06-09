import uuid

from app.domain.entities import TeamEntity
from app.engine.match_prediction import MatchPredictionEngine


class TestFullPrediction:
    def setup_method(self):
        self.engine = MatchPredictionEngine()

    def test_full_prediction_has_all_fields(self):
        home = TeamEntity(id=uuid.uuid4(), name="Brazil", fifa_code="BRA", elo_score=2100, igf_score=90)
        away = TeamEntity(id=uuid.uuid4(), name="Bolivia", fifa_code="BOL", elo_score=1300, igf_score=20)

        result = self.engine.predict_full(home, away)
        assert result.top_10_scores is not None
        assert len(result.top_10_scores) >= 1
        assert result.confidence_index > 0
        assert result.confidence_level != ""
        assert result.surprise_risk > 0
        assert result.btts_prob >= 0
        assert result.over_25_prob >= 0
        assert result.under_25_prob >= 0
        assert result.home_clean_sheet >= 0
        assert result.away_clean_sheet >= 0

    def test_top_10_scores_ordered(self):
        home = TeamEntity(id=uuid.uuid4(), name="Germany", elo_score=1950, igf_score=80)
        away = TeamEntity(id=uuid.uuid4(), name="San Marino", elo_score=800, igf_score=10)

        result = self.engine.predict_full(home, away)
        assert len(result.top_10_scores) >= 5
        for i in range(len(result.top_10_scores) - 1):
            assert result.top_10_scores[i][1] >= result.top_10_scores[i + 1][1]

    def test_confidence_index_strong_favorite(self):
        home = TeamEntity(id=uuid.uuid4(), name="France", elo_score=2050, igf_score=95)
        away = TeamEntity(id=uuid.uuid4(), name="Haiti", elo_score=1100, igf_score=15)

        result = self.engine.predict_full(home, away)
        assert result.confidence_index > 60
        assert result.confidence_level in ["Alta", "Muy Alta"]

    def test_confidence_index_equal_teams(self):
        home = TeamEntity(id=uuid.uuid4(), name="Team A", elo_score=1500, igf_score=50)
        away = TeamEntity(id=uuid.uuid4(), name="Team B", elo_score=1500, igf_score=50)

        result = self.engine.predict_full(home, away, home_advantage=False)
        assert result.confidence_index < 30
        assert result.confidence_level in ["Baja", "Muy Baja"]

    def test_surprise_risk(self):
        home = TeamEntity(id=uuid.uuid4(), name="Strong", elo_score=2000, igf_score=90)
        away = TeamEntity(id=uuid.uuid4(), name="Weak", elo_score=900, igf_score=10)

        result = self.engine.predict_full(home, away)
        assert result.surprise_risk < 0.5

    def test_betting_markets(self):
        home = TeamEntity(id=uuid.uuid4(), name="Team A", elo_score=1700, igf_score=60)
        away = TeamEntity(id=uuid.uuid4(), name="Team B", elo_score=1600, igf_score=50)

        result = self.engine.predict_full(home, away)
        assert 0 <= result.btts_prob <= 1
        assert 0 <= result.over_25_prob <= 1
        assert 0 <= result.under_25_prob <= 1
        assert abs(result.over_25_prob + result.under_25_prob - 1.0) < 0.01
