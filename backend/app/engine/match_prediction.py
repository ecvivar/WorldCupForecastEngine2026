"""
Match Prediction Engine.

Implements:
- Poisson regression (independent goals)
- Dixon-Coles (low-score correction)
- Elo-based probability
- Bayesian updating (prior + observed)
- Confidence Index, Surprise Risk, betting markets

All methods return full MatchPredictionResult with all derived metrics.
"""

import logging
from dataclasses import dataclass
from math import exp, factorial

import numpy as np

from app.domain.entities import ConfidenceLevel, MatchPredictionResult, TeamEntity

logger = logging.getLogger(__name__)


@dataclass
class MatchPredictionConfig:
    max_goals: int = 10
    dixon_coles_tau: float = 0.1
    elo_k_factor: int = 32
    home_advantage: float = 0.08
    bayesian_prior_strength: float = 2.0
    top_n_scores: int = 10
    calibration_adjustments: dict | None = None


class MatchPredictionEngine:
    """Computes match outcome probabilities using multiple methods."""

    def __init__(self, config: MatchPredictionConfig | None = None):
        self.config = config or MatchPredictionConfig()

    def predict_full(
        self,
        home_team: TeamEntity,
        away_team: TeamEntity,
        home_advantage: bool = True,
    ) -> MatchPredictionResult:
        """
        Full prediction pipeline:
        1. Poisson baseline with Dixon-Coles adjustment
        2. Bayesian update using historical variance prior
        3. Confidence Index calculation
        4. Surprise Risk calculation
        5. Betting market probabilities (BTTS, Over/Under, CS)
        """
        # Step 1: Dixon-Coles adjusted prediction
        dc_result = self.predict_dixon_coles(home_team, away_team, home_advantage)

        # Step 2: Bayesian update
        bayes = self._bayesian_update(
            dc_result.home_win_prob,
            dc_result.draw_prob,
            dc_result.away_win_prob,
            home_team.elo_score,
            away_team.elo_score,
        )

        # Step 3: Confidence Index (0-100)
        confidence = self._compute_confidence(
            home_team.elo_score,
            away_team.elo_score,
            home_team.igf_score,
            away_team.igf_score,
        )

        confidence_level = self._classify_confidence(confidence)

        # Step 3b: Calibration adjustments (from historical bias analysis)
        if self.config.calibration_adjustments:
            adjusted_probs = self._apply_calibration_adjustments(
                bayes["home_win"], bayes["draw"], bayes["away_win"],
                self.config.calibration_adjustments,
            )
            bayes = adjusted_probs

        # Step 4: Surprise Risk
        surprise = self._compute_surprise_risk(
            bayes["home_win"], bayes["away_win"], bayes["draw"]
        )

        # Step 5: Betting markets
        btts = self._compute_btts(
            dc_result.score_probabilities
            if dc_result.score_probabilities
            else {}
        )
        over_25, under_25, over_35 = self._compute_goal_markets(
            dc_result.score_probabilities
            if dc_result.score_probabilities
            else {}
        )
        home_cs, away_cs = self._compute_clean_sheets(
            dc_result.score_probabilities
            if dc_result.score_probabilities
            else {}
        )

        # Step 6: Top 10 ordered scores
        top_10 = self._top_n_scores(
            dc_result.score_probabilities
            if dc_result.score_probabilities
            else {}
        )

        return MatchPredictionResult(
            match_id=dc_result.match_id,
            home_team=dc_result.home_team,
            away_team=dc_result.away_team,
            home_win_prob=round(bayes["home_win"], 4),
            draw_prob=round(bayes["draw"], 4),
            away_win_prob=round(bayes["away_win"], 4),
            home_expected_goals=dc_result.home_expected_goals,
            away_expected_goals=dc_result.away_expected_goals,
            most_likely_score=top_10[0][0] if top_10 else "",
            score_probabilities=dc_result.score_probabilities,
            top_10_scores=top_10,
            confidence_index=round(confidence, 2),
            confidence_level=confidence_level,
            surprise_risk=round(surprise, 4),
            btts_prob=round(btts, 4),
            over_25_prob=round(over_25, 4),
            over_35_prob=round(over_35, 4),
            under_25_prob=round(under_25, 4),
            home_clean_sheet=round(home_cs, 4),
            away_clean_sheet=round(away_cs, 4),
        )

    def predict_poisson(
        self,
        home_team: TeamEntity,
        away_team: TeamEntity,
        home_advantage: bool = True,
    ) -> MatchPredictionResult:
        home_strength = home_team.igf_score / 50.0
        away_strength = away_team.igf_score / 50.0
        ha = self.config.home_advantage if home_advantage else 0.0

        lambda_home = max(0.1, exp(home_strength - away_strength + ha))
        lambda_away = max(0.1, exp(away_strength - home_strength))

        probs = self._compute_poisson_matrix(lambda_home, lambda_away)
        home_win = probs["home_win"]
        draw = probs["draw"]
        away_win = probs["away_win"]

        expected_home = sum(i * p for i, p in enumerate(probs["home_goal_dist"]))
        expected_away = sum(j * p for j, p in enumerate(probs["away_goal_dist"]))

        likely_score = self._most_likely_score(probs["matrix"])
        top_10 = self._top_n_scores(probs["score_probs"])

        return MatchPredictionResult(
            match_id=home_team.id,
            home_team=home_team.name,
            away_team=away_team.name,
            home_win_prob=round(home_win, 4),
            draw_prob=round(draw, 4),
            away_win_prob=round(away_win, 4),
            home_expected_goals=round(expected_home, 4),
            away_expected_goals=round(expected_away, 4),
            most_likely_score=likely_score,
            score_probabilities=probs["score_probs"],
            top_10_scores=top_10,
        )

    def predict_dixon_coles(
        self,
        home_team: TeamEntity,
        away_team: TeamEntity,
        home_advantage: bool = True,
    ) -> MatchPredictionResult:
        base = self.predict_poisson(home_team, away_team, home_advantage)
        rho = self.config.dixon_coles_tau

        adjusted = self._apply_dixon_coles(
            base.score_probabilities or {},
            rho,
        )
        top_10 = self._top_n_scores(adjusted["score_probs"])

        return MatchPredictionResult(
            match_id=base.match_id,
            home_team=base.home_team,
            away_team=base.away_team,
            home_win_prob=round(adjusted["home_win"], 4),
            draw_prob=round(adjusted["draw"], 4),
            away_win_prob=round(adjusted["away_win"], 4),
            home_expected_goals=base.home_expected_goals,
            away_expected_goals=base.away_expected_goals,
            most_likely_score=adjusted["most_likely"],
            score_probabilities=adjusted["score_probs"],
            top_10_scores=top_10,
        )

    def predict_elo(
        self,
        home_team: TeamEntity,
        away_team: TeamEntity,
        home_advantage: bool = True,
    ) -> MatchPredictionResult:
        ha = 100 if home_advantage else 0
        expected_home = 1.0 / (1.0 + 10.0 ** ((away_team.elo_score - home_team.elo_score + ha) / 400.0))
        expected_away = 1.0 - expected_home
        draw_prob = 0.25 * (1 - abs(expected_home - expected_away))
        home_win = expected_home - draw_prob / 2
        away_win = expected_away - draw_prob / 2

        return MatchPredictionResult(
            match_id=home_team.id,
            home_team=home_team.name,
            away_team=away_team.name,
            home_win_prob=round(max(0.0, home_win), 4),
            draw_prob=round(max(0.0, draw_prob), 4),
            away_win_prob=round(max(0.0, away_win), 4),
            home_expected_goals=round(expected_home * 3, 4),
            away_expected_goals=round(expected_away * 3, 4),
            most_likely_score="",
            score_probabilities=None,
        )

    def _compute_poisson_matrix(self, lambda_home: float, lambda_away: float) -> dict:
        max_g = self.config.max_goals
        home_goal_dist = np.array(
            [self._poisson_pmf(i, lambda_home) for i in range(max_g + 1)]
        )
        away_goal_dist = np.array(
            [self._poisson_pmf(j, lambda_away) for j in range(max_g + 1)]
        )

        matrix = np.outer(home_goal_dist, away_goal_dist)

        # triu_indices: row < col  => home < away => away win
        # tril_indices: row > col  => home > away => home win
        away_win = np.sum(matrix[np.triu_indices(max_g + 1, k=1)])
        draw = np.sum(np.diag(matrix))
        home_win = np.sum(matrix[np.tril_indices(max_g + 1, k=-1)])

        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total

        score_probs = {}
        for i in range(max_g + 1):
            for j in range(max_g + 1):
                score_probs[f"{i}-{j}"] = float(matrix[i, j] / total if total > 0 else 0)

        return {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "home_goal_dist": home_goal_dist.tolist(),
            "away_goal_dist": away_goal_dist.tolist(),
            "matrix": matrix,
            "score_probs": score_probs,
        }

    @staticmethod
    def _poisson_pmf(k: int, lam: float) -> float:
        return (lam ** k) * exp(-lam) / factorial(k)

    @staticmethod
    def _most_likely_score(matrix: np.ndarray) -> str:
        idx = np.unravel_index(np.argmax(matrix), matrix.shape)
        return f"{idx[0]}-{idx[1]}"

    @staticmethod
    def _top_n_scores(score_probs: dict[str, float], n: int = 10) -> list[tuple[str, float]]:
        sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)
        return [(s, round(p, 6)) for s, p in sorted_scores[:n]]

    @staticmethod
    def _apply_dixon_coles(score_probs: dict[str, float], rho: float) -> dict:
        if not score_probs:
            return {"home_win": 0, "draw": 0, "away_win": 0, "most_likely": "", "score_probs": {}}

        adjusted = {}
        for score, prob in score_probs.items():
            i, j = map(int, score.split("-"))
            if i == 0 and j == 0:
                adjusted[score] = prob * (1 - rho)
            elif i == 0 and j == 1:
                adjusted[score] = prob * (1 + rho)
            elif i == 1 and j == 0:
                adjusted[score] = prob * (1 + rho)
            elif i == 1 and j == 1:
                adjusted[score] = prob * (1 - rho)
            else:
                adjusted[score] = prob

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        home_win = sum(v for k, v in adjusted.items() if int(k.split("-")[0]) > int(k.split("-")[1]))
        draw = sum(v for k, v in adjusted.items() if int(k.split("-")[0]) == int(k.split("-")[1]))
        away_win = sum(v for k, v in adjusted.items() if int(k.split("-")[0]) < int(k.split("-")[1]))

        most_likely = max(adjusted, key=adjusted.get)

        return {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "most_likely": most_likely,
            "score_probs": adjusted,
        }

    @staticmethod
    def _bayesian_update(
        home_win: float, draw: float, away_win: float,
        elo_home: int, elo_away: int,
        prior_strength: float = 2.0,
    ) -> dict:
        """Bayesian update using Elo difference as prior."""
        elo_diff = elo_home - elo_away
        elo_expected_home = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))

        prior_home = elo_expected_home
        prior_draw = 0.25
        prior_away = 1.0 - prior_home - prior_draw
        if prior_away < 0.0:
            prior_away = 0.0
            total_prior = prior_home + prior_draw + prior_away
            prior_home /= total_prior
            prior_draw /= total_prior

        total = prior_strength + 1.0
        updated_home = (prior_strength * prior_home + home_win) / total
        updated_draw = (prior_strength * prior_draw + draw) / total
        updated_away = (prior_strength * prior_away + away_win) / total

        total_p = updated_home + updated_draw + updated_away
        return {
            "home_win": updated_home / total_p,
            "draw": updated_draw / total_p,
            "away_win": updated_away / total_p,
        }

    @staticmethod
    def _compute_confidence(elo_home: int, elo_away: int, igf_home: float, igf_away: float) -> float:
        """Confidence Index 0-100 based on rating differential and variance."""
        elo_diff = abs(elo_home - elo_away)
        igf_diff = abs(igf_home - igf_away)

        elo_confidence = min(100, elo_diff / 8)
        igf_confidence = min(100, igf_diff * 1.0)

        return 0.5 * elo_confidence + 0.5 * igf_confidence

    @staticmethod
    def _classify_confidence(score: float) -> str:
        if score >= 80:
            return ConfidenceLevel.MUY_ALTA.value
        if score >= 65:
            return ConfidenceLevel.ALTA.value
        if score >= 50:
            return ConfidenceLevel.MEDIA.value
        if score >= 35:
            return ConfidenceLevel.BAJA.value
        return ConfidenceLevel.MUY_BAJA.value

    @staticmethod
    def _apply_calibration_adjustments(
        home_win: float, draw: float, away_win: float,
        adjustments: dict | None = None,
    ) -> dict:
        adj = adjustments or {}
        hw, dw, aw = home_win, draw, away_win

        # Home advantage correction: reduce home when overpredicted
        ha_adj = adj.get("home_advantage_adjustment", 0.0)
        if ha_adj != 0.0:
            hw *= (1.0 + ha_adj)  # negative adj reduces home win
            hw = max(0.0, hw)

        # Draw correction: increase draw when underpredicted
        dr_adj = adj.get("draw_adjustment", 0.0)
        if dr_adj != 0.0:
            dw *= (1.0 + dr_adj)
            dw = max(0.0, dw)

        # Renormalize
        total = hw + dw + aw
        if total > 0:
            hw /= total
            dw /= total
            aw /= total

        return {"home_win": hw, "draw": dw, "away_win": aw}

    @staticmethod
    def _compute_surprise_risk(home_win: float, away_win: float, draw: float) -> float:
        """Probability that the non-favorite gets points."""
        if home_win >= away_win and home_win >= draw:
            return draw + away_win
        elif away_win >= home_win and away_win >= draw:
            return draw + home_win
        else:
            return min(home_win, away_win) + draw

    @staticmethod
    def _compute_btts(score_probs: dict[str, float]) -> float:
        """Both Teams To Score probability."""
        btts = 0.0
        for score, prob in score_probs.items():
            i, j = map(int, score.split("-"))
            if i > 0 and j > 0:
                btts += prob
        return btts

    @staticmethod
    def _compute_goal_markets(score_probs: dict[str, float]) -> tuple[float, float, float]:
        """Over 2.5, Under 2.5, Over 3.5 probabilities."""
        over_25 = 0.0
        over_35 = 0.0
        for score, prob in score_probs.items():
            i, j = map(int, score.split("-"))
            total = i + j
            if total >= 3:
                over_25 += prob
            if total >= 4:
                over_35 += prob
        under_25 = 1.0 - over_25
        return over_25, under_25, over_35

    @staticmethod
    def _compute_clean_sheets(score_probs: dict[str, float]) -> tuple[float, float]:
        """Home clean sheet, Away clean sheet probabilities."""
        home_cs = 0.0
        away_cs = 0.0
        for score, prob in score_probs.items():
            i, j = map(int, score.split("-"))
            if j == 0:
                home_cs += prob
            if i == 0:
                away_cs += prob
        return home_cs, away_cs
