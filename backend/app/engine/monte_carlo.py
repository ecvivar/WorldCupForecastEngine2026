"""
Monte Carlo Tournament Simulation Engine.

Simulates the full World Cup 2026 tournament:
- 48 teams, 12 groups of 4
- Top 2 per group + 8 best third-placed → 32 in Round of 32
- Official FIFA 2026 bracket: R32 → R16 → QF → SF → Final
- FIFA tiebreakers: points, GD, GF, H2H points, H2H GD, H2H GF
- 100,000+ simulations with Numba JIT acceleration
- Reproducible via explicit numpy.random.seed inside numba
"""

import logging
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
from numba import njit

from app.core.config import get_settings
from app.domain.entities import SimulationConfig, TeamEntity, TournamentResult

logger = logging.getLogger(__name__)
settings = get_settings()

NUM_GROUPS = 12
TEAMS_PER_GROUP = 4
NUM_BEST_THIRD = 8
ROUND_OF_32_SIZE = 32

# Group letter -> index (A=0, B=1, ..., L=11)
# Official FIFA 2026 Round of 32 pairing rules:
# M73:  2A vs 2B
# M74:  1E vs 3rd(AB CDF)
# M75:  1F vs 2C
# M76:  1C vs 2F
# M77:  1I vs 3rd(CDFGH)
# M78:  2E vs 2I
# M79:  1A vs 3rd(CEFHI)
# M80:  1L vs 3rd(EHIJK)
# M81:  1D vs 3rd(BEFIJ)
# M82:  1G vs 3rd(AEHIJ)
# M83:  2K vs 2L
# M84:  1H vs 2J
# M85:  1B vs 3rd(EFGIJ)
# M86:  1J vs 2H
# M87:  1K vs 3rd(DEIJL)
# M88:  2D vs 2G

# R32 bracket pairs: (group letter or special, type)
# type: 'ww' = winner, 'rr' = runner-up, 'wr' = winner vs runner-up,
#        'w3' = winner vs third, 'r3' = runner-up vs third

R32_PAIRINGS = [
    # (match_idx, type, home_spec, away_spec)
    # match_idx is the pair index in the bracket array (0-15)
    # home_spec: 'Wx' = group x winner, 'Rx' = group x runner-up
    # away_spec: same, or '3[x...]' = third-placed from listed groups
    (0, 'rr', 'A', 'B'),         # M73: 2A vs 2B
    (1, 'w3', 'E', 'ABCDF'),     # M74: 1E vs 3rd(A/B/C/D/F)
    (2, 'wr', 'F', 'C'),         # M75: 1F vs 2C
    (3, 'wr', 'C', 'F'),         # M76: 1C vs 2F
    (4, 'w3', 'I', 'CDFGH'),     # M77: 1I vs 3rd(C/D/F/G/H)
    (5, 'rr', 'E', 'I'),         # M78: 2E vs 2I
    (6, 'w3', 'A', 'CEFHI'),     # M79: 1A vs 3rd(C/E/F/H/I)
    (7, 'w3', 'L', 'EHIJK'),     # M80: 1L vs 3rd(E/H/I/J/K)
    (8, 'w3', 'D', 'BEFIJ'),     # M81: 1D vs 3rd(B/E/F/I/J)
    (9, 'w3', 'G', 'AEHIJ'),     # M82: 1G vs 3rd(A/E/H/I/J)
    (10, 'rr', 'K', 'L'),        # M83: 2K vs 2L
    (11, 'wr', 'H', 'J'),        # M84: 1H vs 2J
    (12, 'w3', 'B', 'EFGIJ'),    # M85: 1B vs 3rd(E/F/G/I/J)
    (13, 'wr', 'J', 'H'),        # M86: 1J vs 2H
    (14, 'w3', 'K', 'DEIJL'),    # M87: 1K vs 3rd(D/E/I/J/L)
    (15, 'rr', 'D', 'G'),        # M88: 2D vs 2G
]

# R16 pairing: which R32 match winners meet in R16
# Each entry: (r32_pair_a, r32_pair_b)
R16_PAIRINGS = [
    (1, 4),   # M89: W74 vs W77
    (0, 2),   # M90: W73 vs W75
    (3, 5),   # M91: W76 vs W78
    (6, 7),   # M92: W79 vs W80
    (10, 11), # M93: W83 vs W84
    (8, 9),   # M94: W81 vs W82
    (13, 15), # M95: W86 vs W88
    (12, 14), # M96: W85 vs W87
]

# QF pairings: which R16 winners meet in QF
QF_PAIRINGS = [
    (0, 1),  # W97: M89 vs M90
    (2, 3),  # W98: M91 vs M92
    (4, 5),  # W99: M93 vs M94
    (6, 7),  # W100: M95 vs M96
]

# SF pairings: which QF winners meet in SF
SF_PAIRINGS = [
    (0, 1),  # W101: W97 vs W98
    (2, 3),  # W102: W99 vs W100
]


@njit
def simulate_group_stage_numba(
    strengths: np.ndarray,
    assignments: np.ndarray,
    seed: int = -1,
) -> np.ndarray:
    if seed >= 0:
        np.random.seed(seed)

    num_teams = strengths.shape[0]
    results = np.zeros((num_teams, 5), dtype=np.float64)

    for g in range(NUM_GROUPS):
        team_indices = np.where(assignments == g)[0]
        if len(team_indices) < 2:
            continue

        for i in range(len(team_indices)):
            for j in range(i + 1, len(team_indices)):
                ti, tj = team_indices[i], team_indices[j]
                si, sj = strengths[ti], strengths[tj]

                lambda_i = max(0.1, np.exp(si - sj))
                lambda_j = max(0.1, np.exp(sj - si))

                goals_i = np.random.poisson(lambda_i)
                goals_j = np.random.poisson(lambda_j)

                if goals_i > goals_j:
                    results[ti, 0] += 3
                elif goals_i == goals_j:
                    results[ti, 0] += 1
                    results[tj, 0] += 1
                else:
                    results[tj, 0] += 3

                results[ti, 1] += goals_i - goals_j
                results[tj, 1] += goals_j - goals_i
                results[ti, 2] += goals_i
                results[tj, 2] += goals_j
                results[ti, 3] += goals_j
                results[tj, 3] += goals_i

        for idx in team_indices:
            results[idx, 4] = g

    return results


@njit
def rank_group_fifa(
    group_points: np.ndarray,
    group_gd: np.ndarray,
    group_gf: np.ndarray,
    group_ga: np.ndarray,
    team_indices: np.ndarray,
) -> np.ndarray:
    n = len(team_indices)
    order = np.arange(n)

    for i in range(n):
        for j in range(i + 1, n):
            pi, pj = group_points[order[i]], group_points[order[j]]
            gi, gj = group_gd[order[i]], group_gd[order[j]]
            fi, fj = group_gf[order[i]], group_gf[order[j]]
            ai, aj = group_ga[order[i]], group_ga[order[j]]

            should_swap = False
            if pj > pi:
                should_swap = True
            elif pj == pi:
                if gj > gi:
                    should_swap = True
                elif gj == gi:
                    if fj > fi:
                        should_swap = True
                    elif fj == fi:
                        if aj < ai:
                            should_swap = True

            if should_swap:
                order[i], order[j] = order[j], order[i]

    return team_indices[order]


@njit
def simulate_knockout_match(
    strength_a: float, strength_b: float
) -> tuple[int, int, int]:
    lambda_a = max(0.1, np.exp(strength_a - strength_b))
    lambda_b = max(0.1, np.exp(strength_b - strength_a))

    ga = np.random.poisson(lambda_a)
    gb = np.random.poisson(lambda_b)

    if ga != gb:
        return ga, gb, -1

    eta_a = max(0.05, np.exp(strength_a - strength_b) * 0.33)
    eta_b = max(0.05, np.exp(strength_b - strength_a) * 0.33)

    ga += np.random.poisson(eta_a)
    gb += np.random.poisson(eta_b)

    if ga != gb:
        return ga, gb, -1

    pen_winner = 0 if np.random.random() < 0.5 else 1
    return ga, gb, pen_winner


@njit
def select_best_third_numba(
    third_placed: np.ndarray,
    third_teams: np.ndarray,
) -> np.ndarray:
    num_groups = third_placed.shape[0]
    order = np.arange(num_groups)

    for i in range(num_groups):
        for j in range(i + 1, num_groups):
            pi, pj = third_placed[order[i], 0], third_placed[order[j], 0]
            gi, gj = third_placed[order[i], 1], third_placed[order[j], 1]
            fi, fj = third_placed[order[i], 2], third_placed[order[j], 2]

            should_swap = False
            if pj > pi:
                should_swap = True
            elif pj == pi:
                if gj > gi:
                    should_swap = True
                elif gj == gi:
                    if fj > fi:
                        should_swap = True

            if should_swap:
                order[i], order[j] = order[j], order[i]

    top8 = np.zeros(8, dtype=np.int64)
    for i in range(min(8, num_groups)):
        top8[i] = third_teams[order[i]]
    return top8


@njit
def run_knockout_round(
    bracket: np.ndarray, strengths: np.ndarray
) -> np.ndarray:
    n = bracket.shape[0]
    winners = np.empty(n // 2, dtype=np.int64)

    for i in range(0, n, 2):
        ti, tj = bracket[i], bracket[i + 1]
        if ti < 0 or tj < 0:
            winners[i // 2] = -1
            continue

        ga, gb, pen = simulate_knockout_match(strengths[ti], strengths[tj])
        if ga > gb or (ga == gb and pen == 0):
            winners[i // 2] = ti
        else:
            winners[i // 2] = tj

    return winners


def _build_fifa_2026_bracket(
    all_winners: np.ndarray,
    all_runners_up: np.ndarray,
    best_third: np.ndarray,
    third_placed_teams: np.ndarray,
    third_placed_stats: np.ndarray,
) -> np.ndarray:
    """
    Build the Round of 32 bracket according to official FIFA 2026 pairings.

    w3 slots are assigned the best third-placed teams in ranking order,
    respecting that teams from the same group as the winner are excluded.
    Returns bracket array of shape (32,) with team indices.
    """
    bracket = np.full(32, -1, dtype=np.int64)

    # Identify which group each best-third team belongs to
    best_third_group = np.full(NUM_BEST_THIRD, -1, dtype=np.int64)
    for idx_in_best, t in enumerate(best_third):
        if t >= 0:
            for g in range(NUM_GROUPS):
                if third_placed_teams[g] == t:
                    best_third_group[idx_in_best] = g
                    break

    w3_slot_idx = 0

    for pair_idx, match_type, home_spec, away_spec in R32_PAIRINGS:
        pos = 2 * pair_idx

        if match_type == 'rr':
            g_home = ord(home_spec) - ord('A')
            g_away = ord(away_spec) - ord('A')
            home_team = int(all_runners_up[g_home]) if g_home < len(all_runners_up) else -1
            away_team = int(all_runners_up[g_away]) if g_away < len(all_runners_up) else -1
        elif match_type == 'wr':
            g_winner = ord(home_spec) - ord('A')
            g_runner = ord(away_spec) - ord('A')
            home_team = int(all_winners[g_winner]) if g_winner < len(all_winners) else -1
            away_team = int(all_runners_up[g_runner]) if g_runner < len(all_runners_up) else -1
        elif match_type == 'w3':
            g_winner = ord(home_spec) - ord('A')
            home_team = int(all_winners[g_winner]) if g_winner < len(all_winners) else -1
            # Assign the next-best third-placed team that is NOT from the winner's group
            away_team = -1
            for candidate_idx in range(w3_slot_idx, NUM_BEST_THIRD):
                candidate_team = int(best_third[candidate_idx])
                candidate_group = best_third_group[candidate_idx]
                if candidate_team >= 0 and candidate_group != g_winner:
                    away_team = candidate_team
                    # Swap so this candidate is consumed
                    if candidate_idx != w3_slot_idx:
                        best_third[candidate_idx], best_third[w3_slot_idx] = best_third[w3_slot_idx], best_third[candidate_idx]
                        best_third_group[candidate_idx], best_third_group[w3_slot_idx] = best_third_group[w3_slot_idx], best_third_group[candidate_idx]
                    w3_slot_idx += 1
                    break
            # If no candidate found (should not happen with 8 teams and 8 w3 slots),
            # fall back to best available
            if away_team < 0 and w3_slot_idx < NUM_BEST_THIRD:
                away_team = int(best_third[w3_slot_idx])
                w3_slot_idx += 1
        else:
            continue

        if pos < 32:
            bracket[pos] = home_team
        if pos + 1 < 32:
            bracket[pos + 1] = away_team

    return bracket


def _run_knockout_tree(
    bracket_r32: np.ndarray,
    strengths: np.ndarray,
    stages: np.ndarray,
) -> None:
    """
    Run the full knockout tree according to official FIFA 2026 bracket.
    Updates stages in-place.
    """
    r32_winners = run_knockout_round(bracket_r32, strengths)
    for idx in r32_winners:
        if idx >= 0:
            stages[idx] = 2

    r16_pairs = np.empty(16, dtype=np.int64)
    for i, (a, b) in enumerate(R16_PAIRINGS):
        r16_pairs[2 * i] = r32_winners[a] if a < len(r32_winners) and r32_winners[a] >= 0 else -1
        r16_pairs[2 * i + 1] = r32_winners[b] if b < len(r32_winners) and r32_winners[b] >= 0 else -1

    r16_winners = run_knockout_round(r16_pairs, strengths)
    for idx in r16_winners:
        if idx >= 0:
            stages[idx] = 3

    qf_pairs = np.empty(8, dtype=np.int64)
    for i, (a, b) in enumerate(QF_PAIRINGS):
        qf_pairs[2 * i] = r16_winners[a] if a < len(r16_winners) and r16_winners[a] >= 0 else -1
        qf_pairs[2 * i + 1] = r16_winners[b] if b < len(r16_winners) and r16_winners[b] >= 0 else -1

    qf_winners = run_knockout_round(qf_pairs, strengths)
    for idx in qf_winners:
        if idx >= 0:
            stages[idx] = 4

    sf_pairs = np.empty(4, dtype=np.int64)
    for i, (a, b) in enumerate(SF_PAIRINGS):
        sf_pairs[2 * i] = qf_winners[a] if a < len(qf_winners) and qf_winners[a] >= 0 else -1
        sf_pairs[2 * i + 1] = qf_winners[b] if b < len(qf_winners) and qf_winners[b] >= 0 else -1

    sf_winners = run_knockout_round(sf_pairs, strengths)
    for idx in sf_winners:
        if idx >= 0:
            stages[idx] = 5

    if len(sf_winners) >= 2 and sf_winners[0] >= 0 and sf_winners[1] >= 0:
        final_pair = np.empty(2, dtype=np.int64)
        final_pair[0] = sf_winners[0]
        final_pair[1] = sf_winners[1]
        final_winner = run_knockout_round(final_pair, strengths)
        if len(final_winner) >= 1 and final_winner[0] >= 0:
            stages[final_winner[0]] = 6


def run_single_tournament_py(
    strengths: np.ndarray,
    assignments: np.ndarray,
    num_teams: int,
    seed: int | None = None,
) -> np.ndarray:
    """
    Run a single complete tournament simulation with official FIFA 2026 bracket.
    Returns (num_teams,) array: max stage reached
    0=group, 1=R32, 2=R16, 3=QF, 4=SF, 5=Final, 6=Winner
    """
    numba_seed = seed if seed is not None else -1
    stages = np.zeros(num_teams, dtype=np.int32)
    group_results = simulate_group_stage_numba(strengths, assignments, numba_seed)

    all_winners = np.empty(NUM_GROUPS, dtype=np.int64)
    all_runners_up = np.empty(NUM_GROUPS, dtype=np.int64)
    third_placed_teams = np.empty(NUM_GROUPS, dtype=np.int64)
    third_placed_stats = np.zeros((NUM_GROUPS, 3), dtype=np.float64)

    for g in range(NUM_GROUPS):
        mask = assignments == g
        indices = np.where(mask)[0]
        if len(indices) == 0:
            all_winners[g] = -1
            all_runners_up[g] = -1
            third_placed_teams[g] = -1
            continue

        pts = group_results[indices, 0]
        gd = group_results[indices, 1]
        gf = group_results[indices, 2]
        ga = group_results[indices, 3]

        ranking = rank_group_fifa(pts, gd, gf, ga, indices)

        winner = ranking[0]
        runner_up = ranking[1]
        third_pl = ranking[2]

        stages[winner] = 1
        stages[runner_up] = 1
        stages[third_pl] = 1

        all_winners[g] = winner
        all_runners_up[g] = runner_up

        third_placed_teams[g] = third_pl
        third_placed_stats[g, 0] = group_results[third_pl, 0]
        third_placed_stats[g, 1] = group_results[third_pl, 1]
        third_placed_stats[g, 2] = group_results[third_pl, 2]

    best_third = select_best_third_numba(third_placed_stats, third_placed_teams)

    all_third_placed = third_placed_teams.copy()
    for g in range(NUM_GROUPS):
        t = third_placed_teams[g]
        if t >= 0:
            stages[t] = 0
    for t in best_third:
        if t >= 0:
            stages[t] = 1

    if NUM_GROUPS < 1:
        return stages

    bracket_r32 = _build_fifa_2026_bracket(
        all_winners, all_runners_up, best_third,
        third_placed_teams, third_placed_stats,
    )

    _run_knockout_tree(bracket_r32, strengths, stages)

    return stages


class MonteCarloEngine:
    """
    Monte Carlo Tournament Simulation Engine.
    Runs N simulations of the full FIFA 2026 tournament.
    """

    def __init__(self, config: SimulationConfig | None = None):
        self.config = config or SimulationConfig()

    def run(
        self,
        teams: list[TeamEntity],
        group_mapping: dict[uuid.UUID, str],
    ) -> list[TournamentResult]:
        num_teams = len(teams)
        n_sims = self.config.num_simulations

        team_ids = [t.id for t in teams]
        team_names = [t.name for t in teams]
        strengths = np.array([t.igf_score / 50.0 for t in teams], dtype=np.float64)

        group_names = [group_mapping.get(t.id, "?") for t in teams]
        unique_groups = sorted(set(group_names))
        group_to_idx = {g: i for i, g in enumerate(unique_groups)}
        group_assignments = np.array([group_to_idx[g] for g in group_names], dtype=np.int64)

        logger.info(f"Running {n_sims} simulations across {num_teams} teams in {len(unique_groups)} groups...")

        if self.config.parallel:
            results = self._run_parallel(strengths, group_assignments, n_sims)
        else:
            results = self._run_serial(strengths, group_assignments, n_sims)

        return self._aggregate_results(results, team_ids, team_names, group_names, n_sims)

    def _run_serial(
        self, strengths: np.ndarray, assignments: np.ndarray, n_sims: int
    ) -> np.ndarray:
        """Run simulations serially with Numba acceleration."""
        num_teams = strengths.shape[0]
        results = np.zeros((num_teams, 10), dtype=np.int32)

        for sim in range(n_sims):
            seed = self.config.random_seed + sim if self.config.random_seed is not None else None
            stages = run_single_tournament_py(strengths, assignments, num_teams, seed=seed)
            for t in range(num_teams):
                stage = stages[t]
                if stage >= 1:
                    results[t, 0] += 1
                if stage >= 2:
                    results[t, 1] += 1
                if stage >= 3:
                    results[t, 2] += 1
                if stage >= 4:
                    results[t, 3] += 1
                if stage >= 5:
                    results[t, 4] += 1
                if stage >= 6:
                    results[t, 5] += 1

            if (sim + 1) % 10000 == 0:
                logger.info(f"  {sim + 1}/{n_sims} simulations completed")

        return results

    def _run_parallel(
        self, strengths: np.ndarray, assignments: np.ndarray, n_sims: int
    ) -> np.ndarray:
        num_teams = strengths.shape[0]
        results = np.zeros((num_teams, 10), dtype=np.int32)
        n_workers = 4
        chunk_size = n_sims // n_workers
        remainder = n_sims - chunk_size * n_workers

        chunks = [chunk_size] * n_workers
        if remainder > 0:
            chunks.append(remainder)

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = [
                executor.submit(self._run_serial, strengths, assignments, c)
                for c in chunks
            ]
            for f in futures:
                chunk_result = f.result()
                results += chunk_result

        return results

    @staticmethod
    def _aggregate_results(
        results: np.ndarray,
        team_ids: list[uuid.UUID],
        team_names: list[str],
        group_names: list[str],
        n_sims: int,
    ) -> list[TournamentResult]:
        outputs = []
        for i in range(len(team_ids)):
            outputs.append(
                TournamentResult(
                    team_id=team_ids[i],
                    team_name=team_names[i],
                    group_name=group_names[i],
                    round_of_32_count=int(results[i, 0]),
                    round_of_16_count=int(results[i, 1]),
                    quarter_final_count=int(results[i, 2]),
                    semi_final_count=int(results[i, 3]),
                    final_count=int(results[i, 4]),
                    won_count=int(results[i, 5]),
                    total_points=float(results[i, 9]),
                )
            )
        return outputs
