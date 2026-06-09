import uuid

from app.domain.entities import TeamEntity
from app.engine.match_prediction import MatchPredictionEngine


class TestMatchPrediction:
    def setup_method(self):
        self.engine = MatchPredictionEngine()

    def test_poisson_prediction(self):
        home = TeamEntity(id=uuid.uuid4(), name="Brazil", fifa_code="BRA", igf_score=85)
        away = TeamEntity(id=uuid.uuid4(), name="Bolivia", fifa_code="BOL", igf_score=30)

        result = self.engine.predict_poisson(home, away)
        assert result.home_win_prob > result.away_win_prob
        assert result.home_win_prob > 0.4
        assert result.away_win_prob < 0.3
        assert 0 < result.draw_prob < 0.5
        assert result.home_expected_goals > result.away_expected_goals

    def test_elo_prediction(self):
        home = TeamEntity(id=uuid.uuid4(), name="Germany", elo_score=1950)
        away = TeamEntity(id=uuid.uuid4(), name="San Marino", elo_score=800)

        result = self.engine.predict_elo(home, away)
        assert result.home_win_prob > 0.5
        assert result.away_win_prob < 0.2

    def test_dixon_coles_adjustment(self):
        home = TeamEntity(id=uuid.uuid4(), name="Team A", igf_score=60)
        away = TeamEntity(id=uuid.uuid4(), name="Team B", igf_score=55)

        poisson = self.engine.predict_poisson(home, away)
        dc = self.engine.predict_dixon_coles(home, away)
        assert abs(dc.home_win_prob - poisson.home_win_prob) < 0.05

    def test_equal_teams(self):
        home = TeamEntity(id=uuid.uuid4(), name="Team A", igf_score=50)
        away = TeamEntity(id=uuid.uuid4(), name="Team B", igf_score=50)

        result = self.engine.predict_poisson(home, away, home_advantage=False)
        assert abs(result.home_win_prob - result.away_win_prob) < 0.05
        assert result.draw_prob > 0.2
