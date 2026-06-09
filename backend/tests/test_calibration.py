import uuid
from math import isclose

import numpy as np
import pytest

from app.domain.calibration import HistoricalMatchData
from app.domain.entities import TeamEntity
from app.engine.calibration import CalibrationEngine
from app.engine.match_prediction import MatchPredictionEngine


@pytest.fixture
def engine():
    return CalibrationEngine()


@pytest.fixture
def sample_matches():
    return [
        HistoricalMatchData(
            tournament="2022", stage="group",
            home_team="Brazil", away_team="Serbia",
            home_goals=2, away_goals=0,
            home_elo=2200, away_elo=1700,
            home_igf=95, away_igf=50,
        ),
        HistoricalMatchData(
            tournament="2022", stage="group",
            home_team="Argentina", away_team="Saudi Arabia",
            home_goals=1, away_goals=2,
            home_elo=1950, away_elo=1500,
            home_igf=75, away_igf=30,
        ),
        HistoricalMatchData(
            tournament="2022", stage="final",
            home_team="Argentina", away_team="France",
            home_goals=3, away_goals=3,
            home_elo=1950, away_elo=2100,
            home_igf=75, away_igf=90,
        ),
    ]


class TestCalibrationEngine:
    def test_calibrate_returns_report(self, engine, sample_matches):
        report = engine.calibrate(sample_matches)
        assert report.status.value == "completed"
        assert report.match_count == 3
        assert report.overall is not None
        assert 0 <= report.overall.brier_score <= 1
        assert report.overall.log_loss >= 0
        assert 0 <= report.overall.accuracy <= 1

    def test_calibrate_empty_returns_failed(self, engine):
        report = engine.calibrate([])
        assert report.status.value == "failed"

    def test_brier_score_perfect(self, engine):
        pred_probs = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        actuals = np.array([[1, 0, 0], [0, 0, 1]])
        metric = engine._compute_metrics(pred_probs, actuals)
        assert isclose(metric.brier_score, 0.0, abs_tol=0.001)
        assert isclose(metric.accuracy, 1.0, abs_tol=0.001)

    def test_brier_score_worst(self, engine):
        pred_probs = np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        actuals = np.array([[0, 0, 1], [0, 0, 1]])
        metric = engine._compute_metrics(pred_probs, actuals)
        assert metric.brier_score > 0.5
        assert isclose(metric.accuracy, 0.0, abs_tol=0.001)

    def test_log_loss_finite(self, engine):
        pred_probs = np.array([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8]])
        actuals = np.array([[1, 0, 0], [0, 0, 1]])
        metric = engine._compute_metrics(pred_probs, actuals)
        assert metric.log_loss > 0
        assert np.isfinite(metric.log_loss)

    def test_calibration_error_zero_for_perfect(self, engine):
        pred_probs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        actuals = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        metric = engine._compute_metrics(pred_probs, actuals)
        assert isclose(metric.calibration_error, 0.0, abs_tol=0.01)

    def test_calibration_curve(self, engine):
        pred_probs = np.array([[0.9, 0.05, 0.05], [0.8, 0.1, 0.1], [0.3, 0.3, 0.4]])
        actuals = np.array([[1, 0, 0], [1, 0, 0], [0, 0, 1]])
        curve = engine._calibration_curve(pred_probs, actuals, n_bins=5)
        assert len(curve) > 0
        for bin_data in curve:
            assert bin_data.count > 0
            assert 0 <= bin_data.bin_lower <= 1
            assert 0 <= bin_data.bin_upper <= 1

    def test_outcome_onehot(self, engine):
        assert engine._outcome_onehot(3, 1) == (1, 0, 0)
        assert engine._outcome_onehot(0, 0) == (0, 1, 0)
        assert engine._outcome_onehot(1, 2) == (0, 0, 1)

    def test_bias_analysis(self, engine):
        pred = np.array([[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], [0.2, 0.2, 0.6]])
        act = np.array([[1, 0, 0], [1, 0, 0], [0, 0, 1]])
        bias = engine._bias_analysis(pred, act, [70, 65, 55])
        assert isinstance(bias.home_bias, float)
        assert isinstance(bias.favorite_bias, float)

    def test_auc_roc_perfect(self, engine):
        pred = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        act = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        auc = engine._compute_auc_roc(pred, act)
        assert isclose(auc, 1.0, abs_tol=0.01)

    def test_by_tournament(self, engine, sample_matches):
        report = engine.calibrate(sample_matches)
        assert "2022" in report.by_tournament

    def test_by_stage(self, engine, sample_matches):
        report = engine.calibrate(sample_matches)
        assert "group" in report.by_stage
        assert "final" in report.by_stage

    def test_weight_adjustments(self, engine, sample_matches):
        report = engine.calibrate(sample_matches)
        assert isinstance(report.weight_adjustments, dict)

    def test_full_run_with_real_data(self):
        from app.data.historical_matches import ALL_HISTORICAL_MATCHES
        engine = CalibrationEngine()
        report = engine.calibrate(ALL_HISTORICAL_MATCHES)
        assert report.match_count > 50
        assert report.overall.brier_score > 0
        assert report.overall.accuracy > 0
        assert report.overall.log_loss > 0
        assert "2014" in report.by_tournament
        assert "2018" in report.by_tournament
        assert "2022" in report.by_tournament


class TestCalibrationIntegration:
    def test_predict_then_calibrate(self):
        pred_engine = MatchPredictionEngine()
        cal_engine = CalibrationEngine(prediction_engine=pred_engine)
        match = HistoricalMatchData(
            tournament="2022", stage="group",
            home_team="France", away_team="Australia",
            home_goals=4, away_goals=1,
            home_elo=2100, away_elo=1550,
            home_igf=0.90, away_igf=0.35,
        )
        home = TeamEntity(id=uuid.uuid4(), name="France", elo_score=2100, igf_score=0.90)
        away = TeamEntity(id=uuid.uuid4(), name="Australia", elo_score=1550, igf_score=0.35)
        pred = pred_engine.predict_full(home, away)
        assert pred.home_win_prob > 0.5

        report = cal_engine.calibrate([match])
        assert report.match_count == 1
        assert report.overall.brier_score >= 0
