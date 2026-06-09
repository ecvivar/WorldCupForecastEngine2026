import logging
import uuid
from collections import defaultdict

import numpy as np

from app.domain.calibration import (
    BenchmarkReport,
    BiasReport,
    CalibrationBin,
    CalibrationMetric,
    CalibrationReport,
    CalibrationStatus,
    ConfederationBias,
    DrawBias,
    FavoriteBias,
    HistoricalMatchData,
    HomeBias,
    ModelComparisonResult,
    OutcomeCalibrationCurve,
)
from app.domain.entities import MatchPredictionResult, TeamEntity
from app.engine.match_prediction import MatchPredictionConfig, MatchPredictionEngine

logger = logging.getLogger(__name__)

Outcome = tuple[int, int, int]


class CalibrationEngine:
    """Validates prediction model against historical match data."""

    def __init__(self, prediction_engine: MatchPredictionEngine | None = None):
        self.prediction_engine = prediction_engine or MatchPredictionEngine()

    def calibrate(
        self,
        historical_matches: list[HistoricalMatchData],
        home_advantage: bool = False,
        model_type: str = "full",
    ) -> CalibrationReport:
        """
        Run calibration for a specific model type.
        model_type: 'poisson', 'dixon_coles', or 'full' (default).
        """
        predictions, actuals, tournaments, stages, confs_h, confs_a, confidences = (
            self._run_predictions(historical_matches, home_advantage, model_type)
        )

        n = len(predictions)
        if n == 0:
            return CalibrationReport(
                status=CalibrationStatus.FAILED,
                overall=CalibrationMetric(brier_score=0, log_loss=0, accuracy=0, calibration_error=0),
            )

        pred_probs = np.array([(p.home_win_prob, p.draw_prob, p.away_win_prob) for p in predictions])
        actual_arr = np.array(actuals)
        conf_arr = np.array(confidences, dtype=float)

        overall = self._compute_metrics(pred_probs, actual_arr)

        by_tournament = {}
        for t in sorted(set(tournaments)):
            mask = np.array([x == t for x in tournaments])
            if mask.sum() < 2:
                continue
            by_tournament[t] = self._compute_metrics(pred_probs[mask], actual_arr[mask])

        by_stage = {}
        for s in sorted(set(stages)):
            mask = np.array([x == s for x in stages])
            if mask.sum() < 1:
                continue
            by_stage[s] = self._compute_metrics(pred_probs[mask], actual_arr[mask])

        curve = self._calibration_curve(pred_probs, actual_arr)
        outcome_curves = self._outcome_calibration_curves(pred_probs, actual_arr)
        bias = self._bias_analysis(pred_probs, actual_arr, conf_arr)
        conf_biases = self._confederation_bias(pred_probs, actual_arr, confs_h, confs_a)
        fav_biases = self._favorite_bracket_bias(pred_probs, actual_arr)
        draw_detail = self._draw_bias_detail(pred_probs, actual_arr)
        home_detail = self._home_bias_detail(pred_probs, actual_arr)
        adjustments = self._suggest_adjustments(bias, draw_detail, home_detail)

        return CalibrationReport(
            status=CalibrationStatus.COMPLETED,
            overall=overall,
            by_tournament=by_tournament,
            by_stage=by_stage,
            calibration_curve=curve,
            outcome_curves=outcome_curves,
            bias=bias,
            confederation_biases=conf_biases,
            favorite_biases=fav_biases,
            draw_bias_detail=draw_detail,
            home_bias_detail=home_detail,
            match_count=n,
            weight_adjustments=adjustments,
        )

    def benchmark(
        self,
        historical_matches: list[HistoricalMatchData],
        home_advantage: bool = False,
    ) -> CalibrationReport:
        """Run calibration for all 4 models and produce a benchmark report."""
        models = ["elo", "poisson", "dixon_coles", "full"]
        results: list[ModelComparisonResult] = []

        for model_name in models:
            predictions, actuals, tournaments, stages, _, _, _ = (
                self._run_predictions(historical_matches, home_advantage, model_name)
            )
            n = len(predictions)
            if n == 0:
                continue
            pred_probs = np.array([(p.home_win_prob, p.draw_prob, p.away_win_prob) for p in predictions])
            actual_arr = np.array(actuals)
            overall = self._compute_metrics(pred_probs, actual_arr)

            by_tournament = {}
            for t in sorted(set(tournaments)):
                mask = np.array([x == t for x in tournaments])
                if mask.sum() < 2:
                    continue
                by_tournament[t] = self._compute_metrics(pred_probs[mask], actual_arr[mask])

            by_stage = {}
            for s in sorted(set(stages)):
                mask = np.array([x == s for x in stages])
                if mask.sum() < 1:
                    continue
                by_stage[s] = self._compute_metrics(pred_probs[mask], actual_arr[mask])

            results.append(ModelComparisonResult(
                model_name=model_name, overall=overall,
                by_tournament=by_tournament, by_stage=by_stage,
            ))

        best_model = ""
        improvement = {}
        if len(results) >= 3:
            baseline = results[0].overall.brier_score
            best = min(results, key=lambda r: r.overall.brier_score)
            best_model = best.model_name
            for r in results:
                imp = (baseline - r.overall.brier_score) / baseline * 100 if baseline > 0 else 0
                improvement[r.model_name] = round(imp, 2)

        benchmark = BenchmarkReport(models=results, best_model=best_model, improvement_vs_baseline=improvement)

        default_result = self.calibrate(historical_matches, home_advantage, "full")
        default_result.benchmark = benchmark
        return default_result

    def _run_predictions(
        self, matches: list[HistoricalMatchData],
        home_advantage: bool, model_type: str,
    ):
        predictions: list[MatchPredictionResult] = []
        actuals: list[Outcome] = []
        tournaments: list[str] = []
        stages: list[str] = []
        confs_h: list[str] = []
        confs_a: list[str] = []
        confidences: list[float] = []

        for match in matches:
            home_entity = TeamEntity(
                id=uuid.uuid4(), name=match.home_team,
                elo_score=match.home_elo, igf_score=match.home_igf,
            )
            away_entity = TeamEntity(
                id=uuid.uuid4(), name=match.away_team,
                elo_score=match.away_elo, igf_score=match.away_igf,
            )

            if model_type == "elo":
                pred = self.prediction_engine.predict_elo(home_entity, away_entity, home_advantage)
            elif model_type == "poisson":
                pred = self.prediction_engine.predict_poisson(home_entity, away_entity, home_advantage)
            elif model_type == "dixon_coles":
                pred = self.prediction_engine.predict_dixon_coles(home_entity, away_entity, home_advantage)
            else:
                pred = self.prediction_engine.predict_full(home_entity, away_entity, home_advantage)

            predictions.append(pred)
            actuals.append(self._outcome_onehot(match.home_goals, match.away_goals))
            tournaments.append(match.tournament)
            stages.append(match.stage)
            confs_h.append(match.home_confederation or "")
            confs_a.append(match.away_confederation or "")
            confidences.append(pred.confidence_index)

        return predictions, actuals, tournaments, stages, confs_h, confs_a, confidences

    def _compute_metrics(self, pred_probs: np.ndarray, actuals: np.ndarray) -> CalibrationMetric:
        n = pred_probs.shape[0]
        if n == 0:
            return CalibrationMetric(brier_score=0, log_loss=0, accuracy=0, calibration_error=0)

        brier = float(np.mean(np.sum((pred_probs - actuals) ** 2, axis=1)))

        eps = 1e-15
        clipped = np.clip(pred_probs, eps, 1 - eps)
        log_loss_val = float(-np.mean(np.sum(actuals * np.log(clipped), axis=1)))

        pred_class = np.argmax(pred_probs, axis=1)
        actual_class = np.argmax(actuals, axis=1)
        acc = float(np.mean(pred_class == actual_class))

        cal_error = self._expected_calibration_error(pred_probs, actuals)
        auc = self._compute_auc_roc(pred_probs, actuals)

        return CalibrationMetric(
            brier_score=round(brier, 4),
            log_loss=round(log_loss_val, 4),
            accuracy=round(acc, 4),
            calibration_error=round(cal_error, 4),
            auc_roc=round(auc, 4),
            n_matches=n,
        )

    @staticmethod
    def _compute_auc_roc(pred_probs: np.ndarray, actuals: np.ndarray) -> float:
        n_classes = pred_probs.shape[1]
        aucs = []
        for c in range(n_classes):
            y_true = actuals[:, c]
            y_score = pred_probs[:, c]
            order = np.argsort(y_score)[::-1]
            y_true_sorted = y_true[order]
            tpr, fpr = [0.0], [0.0]
            pos = float(np.sum(y_true_sorted))
            neg = float(len(y_true_sorted) - pos)
            if pos == 0 or neg == 0:
                continue
            tp, fp = 0.0, 0.0
            for v in y_true_sorted:
                if v == 1:
                    tp += 1
                else:
                    fp += 1
                tpr.append(tp / pos)
                fpr.append(fp / neg)
            auc_val = float(np.trapz(tpr, fpr))
            aucs.append(auc_val)
        return float(np.mean(aucs)) if aucs else 0.0

    @staticmethod
    def _expected_calibration_error(pred_probs: np.ndarray, actuals: np.ndarray, n_bins: int = 10) -> float:
        confidences = np.max(pred_probs, axis=1)
        correct = np.argmax(pred_probs, axis=1) == np.argmax(actuals, axis=1)
        bins = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            in_bin = (confidences > bins[i]) & (confidences <= bins[i + 1])
            if np.any(in_bin):
                acc_bin = float(np.mean(correct[in_bin]))
                conf_bin = float(np.mean(confidences[in_bin]))
                ece += len(confidences[in_bin]) * abs(acc_bin - conf_bin)
        return ece / len(confidences) if len(confidences) > 0 else 0.0

    @staticmethod
    def _calibration_curve(pred_probs: np.ndarray, actuals: np.ndarray, n_bins: int = 10) -> list[CalibrationBin]:
        confidences = np.max(pred_probs, axis=1)
        correct = np.argmax(pred_probs, axis=1) == np.argmax(actuals, axis=1)
        bins = np.linspace(0, 1, n_bins + 1)
        curve = []
        for i in range(n_bins):
            in_bin = (confidences > bins[i]) & (confidences <= bins[i + 1])
            count = int(np.sum(in_bin))
            if count > 0:
                curve.append(CalibrationBin(
                    bin_lower=round(bins[i], 2), bin_upper=round(bins[i + 1], 2),
                    count=count,
                    mean_predicted=round(float(np.mean(confidences[in_bin])), 4),
                    mean_actual=round(float(np.mean(correct[in_bin])), 4),
                ))
        return curve

    @staticmethod
    def _outcome_calibration_curves(
        pred_probs: np.ndarray, actuals: np.ndarray, n_bins: int = 10,
    ) -> list[OutcomeCalibrationCurve]:
        """Per-outcome calibration curves (home, draw, away)."""
        labels = ["home", "draw", "away"]
        curves = []
        bins = np.linspace(0, 1, n_bins + 1)

        for c in range(3):
            outcome_probs = pred_probs[:, c]
            outcome_actual = actuals[:, c]
            curve_bins = []
            for i in range(n_bins):
                in_bin = (outcome_probs > bins[i]) & (outcome_probs <= bins[i + 1])
                count = int(np.sum(in_bin))
                if count > 0:
                    curve_bins.append(CalibrationBin(
                        bin_lower=round(bins[i], 2), bin_upper=round(bins[i + 1], 2),
                        count=count,
                        mean_predicted=round(float(np.mean(outcome_probs[in_bin])), 4),
                        mean_actual=round(float(np.mean(outcome_actual[in_bin])), 4),
                    ))
            curves.append(OutcomeCalibrationCurve(outcome=labels[c], bins=curve_bins))
        return curves

    @staticmethod
    def _bias_analysis(pred_probs: np.ndarray, actuals: np.ndarray, confidences: np.ndarray | list) -> BiasReport:
        confidences = np.asarray(confidences, dtype=float)
        pred_class = np.argmax(pred_probs, axis=1)
        actual_class = np.argmax(actuals, axis=1)
        n = len(pred_class)
        if n == 0:
            return BiasReport(home_bias=0, favorite_bias=0, draw_bias=0, underdog_bias=0, high_confidence_bias=0, low_confidence_bias=0)

        pred_home = np.mean(pred_class == 0)
        actual_home = np.mean(actual_class == 0)
        home_bias = round(float(pred_home - actual_home), 4)

        favorite_mask = np.max(pred_probs, axis=1) > 0.5
        fav_correct = float(np.mean(pred_class[favorite_mask] == actual_class[favorite_mask])) if np.any(favorite_mask) else 0.0

        pred_draw = np.mean(pred_class == 1)
        actual_draw = np.mean(actual_class == 1)
        draw_bias = round(float(pred_draw - actual_draw), 4)

        underdog_mask = np.max(pred_probs, axis=1) < 0.5
        underdog_rate = float(np.mean(
            np.argmax(pred_probs[underdog_mask], axis=1) == np.argmax(actuals[underdog_mask], axis=1)
        )) if np.any(underdog_mask) else 0.0

        high_mask = confidences > 65
        low_mask = confidences < 35
        high_bias = float(np.mean(pred_class[high_mask] == actual_class[high_mask])) if np.any(high_mask) else 0.0
        low_bias = float(np.mean(pred_class[low_mask] == actual_class[low_mask])) if np.any(low_mask) else 0.0

        return BiasReport(
            home_bias=home_bias, favorite_bias=round(fav_correct, 4),
            draw_bias=draw_bias, underdog_bias=round(underdog_rate, 4),
            high_confidence_bias=round(high_bias, 4), low_confidence_bias=round(low_bias, 4),
        )

    @staticmethod
    def _confederation_bias(
        pred_probs: np.ndarray, actuals: np.ndarray,
        confs_h: list[str], confs_a: list[str],
    ) -> list[ConfederationBias]:
        """Compute bias per confederation."""
        all_confs = set(confs_h + confs_a) - {""}
        results = []
        for conf in sorted(all_confs):
            mask_h = np.array([c == conf for c in confs_h])
            mask_a = np.array([c == conf for c in confs_a])
            mask = mask_h | mask_a
            n = int(mask.sum())
            if n < 3:
                continue
            sub_pred = pred_probs[mask]
            sub_act = actuals[mask]
            pred_class = np.argmax(sub_pred, axis=1)
            actual_class = np.argmax(sub_act, axis=1)
            brier = float(np.mean(np.sum((sub_pred - sub_act) ** 2, axis=1)))
            acc = float(np.mean(pred_class == actual_class))

            is_home = mask_h[mask]
            home_win_pred = float(np.mean(sub_pred[is_home, 0])) if is_home.any() else 0
            home_win_actual = float(np.mean(sub_act[is_home, 0])) if is_home.any() else 0

            # Compare avg predicted max probability vs accuracy to detect over/underconfidence
            fav_pred = float(np.mean(np.max(sub_pred, axis=1)))
            fav_act = float(np.mean(pred_class == actual_class))

            draw_pred_rate = float(np.mean(pred_class == 1))
            draw_actual_rate = float(np.mean(actual_class == 1))

            results.append(ConfederationBias(
                confederation=conf, match_count=n,
                brier_score=round(brier, 4), accuracy=round(acc, 4),
                home_win_pred=round(home_win_pred, 4), home_win_actual=round(home_win_actual, 4),
                favorite_pred=round(fav_pred, 4), favorite_actual=round(fav_act, 4),
                draw_pred=round(draw_pred_rate, 4), draw_actual=round(draw_actual_rate, 4),
            ))
        return results

    @staticmethod
    def _favorite_bracket_bias(pred_probs: np.ndarray, actuals: np.ndarray) -> list[FavoriteBias]:
        """Bin matches by predicted favorite probability, track actual win rate."""
        max_probs = np.max(pred_probs, axis=1)
        actual_class = np.argmax(actuals, axis=1)
        pred_class = np.argmax(pred_probs, axis=1)

        brackets = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
        results = []
        for lo, hi in brackets:
            mask = (max_probs > lo) & (max_probs <= hi)
            n = int(mask.sum())
            if n < 2:
                continue
            mean_pred = float(np.mean(max_probs[mask]))
            # actual win rate of the predicted favorite
            fav_win = float(np.mean(pred_class[mask] == actual_class[mask]))
            results.append(FavoriteBias(
                bracket_lower=lo, bracket_upper=hi, count=n,
                mean_predicted_prob=round(mean_pred, 4), mean_actual_win_rate=round(fav_win, 4),
            ))
        return results

    @staticmethod
    def _draw_bias_detail(pred_probs: np.ndarray, actuals: np.ndarray) -> DrawBias:
        actual_class = np.argmax(actuals, axis=1)
        pred_draw_rate = float(np.mean(pred_probs[:, 1]))
        actual_draw_rate = float(np.mean(actual_class == 1))
        return DrawBias(
            match_count=len(pred_probs),
            predicted_draw_rate=round(pred_draw_rate, 4),
            actual_draw_rate=round(actual_draw_rate, 4),
            bias=round(pred_draw_rate - actual_draw_rate, 4),
        )

    @staticmethod
    def _home_bias_detail(pred_probs: np.ndarray, actuals: np.ndarray) -> HomeBias:
        actual_class = np.argmax(actuals, axis=1)
        pred_home_rate = float(np.mean(pred_probs[:, 0]))
        actual_home_rate = float(np.mean(actual_class == 0))
        return HomeBias(
            match_count=len(pred_probs),
            predicted_home_win_rate=round(pred_home_rate, 4),
            actual_home_win_rate=round(actual_home_rate, 4),
            bias=round(pred_home_rate - actual_home_rate, 4),
        )

    @staticmethod
    def _suggest_adjustments(
        bias: BiasReport, draw_detail: DrawBias, home_detail: HomeBias,
    ) -> dict[str, float]:
        adjustments = {}
        if abs(home_detail.bias) > 0.03:
            adjustments["home_advantage_adjustment"] = round(-home_detail.bias * 0.5, 4)
        if bias.favorite_bias < 0.5:
            adjustments["favorite_calibration_factor"] = 0.95
        if abs(draw_detail.bias) > 0.02:
            adjustments["draw_adjustment"] = round(-draw_detail.bias * 0.5, 4)
        return adjustments

    @staticmethod
    def _outcome_onehot(home_goals: int, away_goals: int) -> Outcome:
        if home_goals > away_goals:
            return (1, 0, 0)
        elif home_goals == away_goals:
            return (0, 1, 0)
        return (0, 0, 1)
