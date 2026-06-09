"""
Phase 7.6 - End-to-End Tournament Validation & Release Candidate Audit

Validates: simulations (1, 10k, 50k, 100k), match predictions, Monte Carlo correctness,
calibration, performance. Outputs structured results for the final audit report.
"""

import sys, os, time, gc, math, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import uuid

from app.domain.entities import TeamEntity, SimulationConfig, MatchPredictionResult
from app.engine.match_prediction import MatchPredictionEngine
from app.engine.monte_carlo import MonteCarloEngine
from app.engine.calibration import CalibrationEngine
from app.data.historical_matches import ALL_HISTORICAL_MATCHES

###############################################################################
# TEAM ROSTER - 48 teams, 12 groups, realistic Elo & IGF (0-100 scale)
###############################################################################

TEAMS_DATA = {
    "A": [
        ("Mexico", "MEX", 1750, 75, "North America"),
        ("South Africa", "RSA", 1480, 45, "CAF"),
        ("South Korea", "KOR", 1550, 55, "AFC"),
        ("Czech Republic", "CZE", 1600, 60, "UEFA"),
    ],
    "B": [
        ("Canada", "CAN", 1600, 58, "North America"),
        ("Bosnia and Herzegovina", "BIH", 1580, 55, "UEFA"),
        ("Qatar", "QAT", 1450, 40, "AFC"),
        ("Switzerland", "SUI", 1750, 72, "UEFA"),
    ],
    "C": [
        ("Brazil", "BRA", 2200, 95, "South America"),
        ("Morocco", "MAR", 1680, 68, "CAF"),
        ("Haiti", "HAI", 1200, 15, "North America"),
        ("Scotland", "SCO", 1550, 52, "UEFA"),
    ],
    "D": [
        ("United States", "USA", 1700, 70, "North America"),
        ("Paraguay", "PAR", 1550, 50, "South America"),
        ("Australia", "AUS", 1520, 48, "OFC"),
        ("Turkey", "TUR", 1620, 62, "UEFA"),
    ],
    "E": [
        ("Germany", "GER", 2000, 88, "UEFA"),
        ("Curacao", "CUW", 1150, 10, "North America"),
        ("Ivory Coast", "CIV", 1580, 56, "CAF"),
        ("Ecuador", "ECU", 1600, 60, "South America"),
    ],
    "F": [
        ("Netherlands", "NED", 1950, 85, "UEFA"),
        ("Japan", "JPN", 1600, 60, "AFC"),
        ("Sweden", "SWE", 1650, 62, "UEFA"),
        ("Tunisia", "TUN", 1520, 48, "CAF"),
    ],
    "G": [
        ("Belgium", "BEL", 1900, 82, "UEFA"),
        ("Egypt", "EGY", 1600, 58, "CAF"),
        ("Iran", "IRN", 1550, 50, "AFC"),
        ("New Zealand", "NZL", 1400, 35, "OFC"),
    ],
    "H": [
        ("Spain", "ESP", 2050, 90, "UEFA"),
        ("Cape Verde", "CPV", 1350, 25, "CAF"),
        ("Saudi Arabia", "KSA", 1480, 42, "AFC"),
        ("Uruguay", "URU", 1800, 78, "South America"),
    ],
    "I": [
        ("France", "FRA", 2100, 92, "UEFA"),
        ("Senegal", "SEN", 1650, 65, "CAF"),
        ("Iraq", "IRQ", 1420, 38, "AFC"),
        ("Norway", "NOR", 1680, 66, "UEFA"),
    ],
    "J": [
        ("Argentina", "ARG", 2150, 93, "South America"),
        ("Algeria", "ALG", 1620, 60, "CAF"),
        ("Austria", "AUT", 1650, 63, "UEFA"),
        ("Jordan", "JOR", 1380, 32, "AFC"),
    ],
    "K": [
        ("Portugal", "POR", 1950, 84, "UEFA"),
        ("DR Congo", "COD", 1450, 40, "CAF"),
        ("Uzbekistan", "UZB", 1400, 35, "AFC"),
        ("Colombia", "COL", 1780, 75, "South America"),
    ],
    "L": [
        ("England", "ENG", 2050, 90, "UEFA"),
        ("Croatia", "CRO", 1800, 78, "UEFA"),
        ("Ghana", "GHA", 1550, 50, "CAF"),
        ("Panama", "PAN", 1350, 28, "North America"),
    ],
}

def build_teams():
    teams = []
    group_mapping = {}
    for group, entries in TEAMS_DATA.items():
        for name, code, elo, igf, conf in entries:
            t = TeamEntity(
                id=uuid.uuid4(),
                name=name,
                fifa_code=code,
                continent=conf,
                elo_score=elo,
                igf_score=float(igf),
            )
            teams.append(t)
            group_mapping[t.id] = group
    return teams, group_mapping


###############################################################################
# VALIDATION HELPERS
###############################################################################

def check_probs_sum_to_1(home, draw, away, label="", tol=1e-9):
    total = home + draw + away
    ok = abs(total - 1.0) < tol
    if not ok:
        print(f"  !! {label}: probabilities sum to {total:.6f} (expected 1.0)")
    return ok

def check_no_nan(*vals):
    for v in vals:
        if isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
            return False
    return True

def fmt_pct(v):
    return f"{v*100:.1f}%"


###############################################################################
# FASE 7.6C - MATCH PREDICTION VALIDATION
###############################################################################

MATCHES_TO_TEST = [
    ("Brazil", "Bolivia"),
    ("France", "Haiti"),
    ("Argentina", "New Zealand"),
    ("England", "San Marino"),
    ("Spain", "Andorra"),
    ("Mexico", "South Africa"),
    ("United States", "Paraguay"),
    ("Brazil", "France"),
    ("Argentina", "England"),
]

def build_team(name):
    """Find or create a TeamEntity by name from our roster, or synthesize."""
    for group, entries in TEAMS_DATA.items():
        for n, code, elo, igf, conf in entries:
            if n.lower() == name.lower():
                return TeamEntity(
                    id=uuid.uuid4(), name=n, fifa_code=code,
                    continent=conf, elo_score=elo, igf_score=float(igf),
                )
    # Synthetic for teams not in tournament (Bolivia, San Marino, Andorra, New Zealand)
    elo_map = {"Bolivia": 1300, "San Marino": 800, "Andorra": 850, "New Zealand": 1400}
    igf_map = {"Bolivia": 28, "San Marino": 5, "Andorra": 8, "New Zealand": 35}
    elo = elo_map.get(name, 1500)
    igf = igf_map.get(name, 40)
    return TeamEntity(
        id=uuid.uuid4(), name=name, fifa_code=name[:3].upper(),
        continent="Unknown", elo_score=elo, igf_score=float(igf),
    )

def validate_match_predictions(mpe):
    print("\n" + "=" * 65)
    print("FASE 7.6C - MATCH PREDICTION VALIDATION")
    print("=" * 65)
    results_list = []
    anomalies = []

    for home_name, away_name in MATCHES_TO_TEST:
        home = build_team(home_name)
        away = build_team(away_name)
        result = mpe.predict_full(home, away)

        label = f"{home_name:25s} vs {away_name:<25s}"
        print(f"\n  {label}")
        print(f"    Home Win: {fmt_pct(result.home_win_prob):>8s}  "
              f"Draw: {fmt_pct(result.draw_prob):>8s}  "
              f"Away Win: {fmt_pct(result.away_win_prob):>8s}   "
              f"xG: {result.home_expected_goals:.2f} - {result.away_expected_goals:.2f}   "
              f"CI: {result.confidence_index:.0f} ({result.confidence_level})")

        # Validation checks
        if not check_probs_sum_to_1(result.home_win_prob, result.draw_prob, result.away_win_prob, label):
            anomalies.append(f"{label}: probs sum != 1")

        if not check_no_nan(result.home_win_prob, result.draw_prob, result.away_win_prob,
                            result.home_expected_goals, result.away_expected_goals):
            anomalies.append(f"{label}: NaN or Inf detected")

        # Strong favorite sanity: home should be favorite if elo/igf much higher
        if home.elo_score > away.elo_score + 200 and home.igf_score > away.igf_score + 15:
            if result.home_win_prob < 0.4:
                anomalies.append(f"{label}: strong favorite home_win_prob={result.home_win_prob:.4f} too low")
            if result.confidence_index < 20:
                anomalies.append(f"{label}: strong favorite CI={result.confidence_index:.0f} too low")
        if abs(home.elo_score - away.elo_score) < 50 and abs(home.igf_score - away.igf_score) < 10:
            if abs(result.home_win_prob - result.away_win_prob) > 0.15:
                anomalies.append(f"{label}: near-equal teams have large win prob gap ({result.home_win_prob:.3f} vs {result.away_win_prob:.3f})")

        results_list.append({
            "match": f"{home_name} vs {away_name}",
            "home_win_pct": round(result.home_win_prob * 100, 1),
            "draw_pct": round(result.draw_prob * 100, 1),
            "away_win_pct": round(result.away_win_prob * 100, 1),
            "xG_home": round(result.home_expected_goals, 2),
            "xG_away": round(result.away_expected_goals, 2),
            "confidence_index": round(result.confidence_index, 0),
            "confidence_level": result.confidence_level,
        })

    print(f"\n  --- Anomalies: {len(anomalies)} ---")
    for a in anomalies:
        print(f"    ! {a}")
    return results_list, anomalies


###############################################################################
# FASE 7.6A - TOURNAMENT SIMULATIONS
###############################################################################

def run_simulation_batch(teams, group_mapping, n_sims, parallel=False, label=""):
    print(f"\n  Running {n_sims:>6d} simulations {label}... ", end="", flush=True)
    mpe = MatchPredictionEngine()
    # Pre-compute strengths from IGF scores
    num_teams = len(teams)
    strengths = np.array([t.igf_score / 50.0 for t in teams], dtype=np.float64)
    group_names = [group_mapping.get(t.id, "?") for t in teams]
    unique_groups = sorted(set(group_names))
    group_to_idx = {g: i for i, g in enumerate(unique_groups)}
    assignments = np.array([group_to_idx[g] for g in group_names], dtype=np.int64)

    config = SimulationConfig(num_simulations=n_sims, use_numba=True, parallel=parallel)
    engine = MonteCarloEngine(config=config)

    t0 = time.time()
    results = engine.run(teams, group_mapping)
    duration = time.time() - t0

    print(f"done in {duration:.2f}s")

    return results, duration, strengths, mpe


def analyze_simulation(results, teams, n_sims, label=""):
    """Analyze simulation results for correctness and extract probabilities."""
    num = len(results)

    # Sort by won_count descending
    sorted_results = sorted(results, key=lambda r: r.won_count, reverse=True)

    champion_probs = []
    finalist_probs = []
    semi_probs = []
    qual_probs = {}

    for r in sorted_results:
        win_pct = r.won_count / n_sims * 100
        final_pct = r.final_count / n_sims * 100
        semi_pct = r.semi_final_count / n_sims * 100
        r32_pct = r.round_of_32_count / n_sims * 100

        team_info = (r.team_name, r.group_name, r.team_id)
        champion_probs.append((r.team_name, win_pct, r.group_name))
        finalist_probs.append((r.team_name, final_pct, r.group_name))
        semi_probs.append((r.team_name, semi_pct, r.group_name))
        qual_probs[r.team_name] = {
            "r32_pct": r32_pct,
            "group": r.group_name,
            "win_pct": win_pct,
            "final_pct": final_pct,
            "semi_pct": semi_pct,
        }

    # Validation checks
    anomalies = []
    total_win_pct = sum(c[1] for c in champion_probs)
    if abs(total_win_pct - 100.0) > 0.1:
        anomalies.append(f"Sum of champion probabilities = {total_win_pct:.2f}% (expected 100%)")

    for r in results:
        stages = [r.round_of_32_count, r.round_of_16_count, r.quarter_final_count,
                   r.semi_final_count, r.final_count, r.won_count]
        for s in stages:
            if s < 0:
                anomalies.append(f"{r.team_name}: negative stage count {s}")
            if s > n_sims:
                anomalies.append(f"{r.team_name}: stage count {s} > n_sims {n_sims}")

        # Monotonic check: won <= final <= semi <= QF <= R16 <= R32
        if not (r.won_count <= r.final_count <= r.semi_final_count <=
                r.quarter_final_count <= r.round_of_16_count <= r.round_of_32_count):
            anomalies.append(f"{r.team_name}: monotonic stage count violation")

    return champion_probs, finalist_probs, semi_probs, qual_probs, anomalies


###############################################################################
# FASE 7.6D - MONTE CARLO CONVERGENCE
###############################################################################

def validate_convergence(sims_10k, sims_50k, sims_100k):
    print("\n" + "=" * 65)
    print("FASE 7.6D - MONTE CARLO CONVERGENCE")
    print("=" * 65)

    # Compare top 10 champion probabilities across sample sizes
    top10_10k = {name: pct for name, pct, _ in sims_10k[:10]}
    top10_50k = {name: pct for name, pct, _ in sims_50k[:10]}
    top10_100k = {name: pct for name, pct, _ in sims_100k[:10]}

    names = set(list(top10_10k.keys()) + list(top10_50k.keys()) + list(top10_100k.keys()))
    max_deltas = []
    print(f"\n  {'Team':20s} {'10k':>8s} {'50k':>8s} {'100k':>8s} {'Deltamax':>8s}")
    print(f"  {'-'*52}")
    for name in sorted(names):
        p10 = top10_10k.get(name, 0)
        p50 = top10_50k.get(name, 0)
        p100 = top10_100k.get(name, 0)
        delta = max(abs(p10 - p50), abs(p50 - p100), abs(p10 - p100))
        max_deltas.append(delta)
        print(f"  {name:20s} {p10:8.2f}% {p50:8.2f}% {p100:8.2f}% {delta:8.3f}%")

    avg_delta = np.mean(max_deltas)
    max_delta = max(max_deltas)
    print(f"\n  Average Delta between sample sizes: {avg_delta:.3f}%")
    print(f"  Max Delta between sample sizes:     {max_delta:.3f}%")
    print(f"  Convergence: {'STABLE' if max_delta < 3.0 else 'INSUFFICIENT'}")

    return {"avg_delta": avg_delta, "max_delta": max_delta}


###############################################################################
# FASE 7.6E - CALIBRATION VALIDATION
###############################################################################

def validate_calibration():
    print("\n" + "=" * 65)
    print("FASE 7.6E - CALIBRATION VALIDATION")
    print("=" * 65)

    engine = CalibrationEngine()
    t0 = time.time()
    report = engine.calibrate(ALL_HISTORICAL_MATCHES, model_type="full")
    dur = time.time() - t0

    print(f"\n  Calibration completed in {dur:.2f}s")
    print(f"  Overall metrics ({report.match_count} matches):")
    print(f"    Accuracy:     {report.overall.accuracy*100:.2f}%")
    print(f"    Brier Score:  {report.overall.brier_score:.4f}")
    print(f"    Log Loss:     {report.overall.log_loss:.4f}")
    print(f"    ECE:          {report.overall.calibration_error:.4f}")
    print(f"    AUC-ROC:      {report.overall.auc_roc:.4f}")

    # Bias analysis
    if report.bias:
        print(f"\n  Bias analysis:")
        print(f"    Home bias:       {report.bias.home_bias:+.4f}")
        print(f"    Favorite bias:   {report.bias.favorite_bias:+.4f}")
        print(f"    Draw bias:       {report.bias.draw_bias:+.4f}")
        print(f"    Underdog bias:   {report.bias.underdog_bias:+.4f}")

    return {
        "accuracy": report.overall.accuracy,
        "brier_score": report.overall.brier_score,
        "log_loss": report.overall.log_loss,
        "ece": report.overall.calibration_error,
        "auc_roc": report.overall.auc_roc,
        "match_count": report.match_count,
        "duration": dur,
    }


###############################################################################
# FASE 7.6F - PERFORMANCE VALIDATION
###############################################################################

def validate_performance():
    print("\n" + "=" * 65)
    print("FASE 7.6F - PERFORMANCE VALIDATION")
    print("=" * 65)

    perf = {}

    # Match prediction performance: 100 predictions
    mpe = MatchPredictionEngine()
    teams_list, _ = build_teams()
    t0 = time.time()
    for i in range(100):
        h = teams_list[i % len(teams_list)]
        a = teams_list[(i + 1) % len(teams_list)]
        mpe.predict_full(h, a)
    pred_time = (time.time() - t0) / 100 * 1000  # ms per prediction
    print(f"\n  Match Prediction (avg of 100): {pred_time:.1f} ms/call")
    perf["match_prediction_ms"] = pred_time

    # Calibration performance
    engine = CalibrationEngine()
    for n in [64, 192]:
        t0 = time.time()
        engine.calibrate(ALL_HISTORICAL_MATCHES[:n], model_type="full")
        dur = time.time() - t0
        print(f"  Calibration ({n} matches): {dur:.3f}s")
    perf["calibration_192s"] = round(dur, 3)

    # Memory estimate for Monte Carlo
    # 48 teams * 10 int32 counters = 1,920 bytes per chunk
    # 100k sims in 4 chunks of 25k each
    mem_per_worker = 48 * 10 * 4  # bytes (int32)
    perf["mc_memory_bytes"] = mem_per_worker * 4
    print(f"  Monte Carlo memory estimate: {mem_per_worker * 4} bytes per result array")

    return perf


###############################################################################
# MAIN
###############################################################################

def main():
    print()
    print("=" * 65)
    print("  WORLD CUP FORECAST ENGINE 2026 - PHASE 7.6 VALIDATION")
    print("=" * 65)

    ###########################################################################
    # Build teams
    ###########################################################################
    print("\n" + "=" * 65)
    print("SETUP - Building 48 teams across 12 groups")
    print("=" * 65)
    teams, group_mapping = build_teams()
    print(f"  Teams: {len(teams)}, Groups: {len(set(group_mapping.values()))}")
    for g in sorted(set(group_mapping.values())):
        g_teams = [t.name for t in teams if group_mapping.get(t.id) == g]
        print(f"    Group {g}: {', '.join(g_teams)}")

    mpe = MatchPredictionEngine()

    ###########################################################################
    # FASE 7.6C - Match Predictions
    ###########################################################################
    match_results, match_anomalies = validate_match_predictions(mpe)

    ###########################################################################
    # FASE 7.6A - Single tournament
    ###########################################################################
    print("\n" + "=" * 65)
    print("FASE 7.6A - SINGLE TOURNAMENT SIMULATION")
    print("=" * 65)
    sim_single, _, _, _ = run_simulation_batch(teams, group_mapping, 1, parallel=False, label="(single)")
    winner = max(sim_single, key=lambda r: r.won_count)
    runner_up = max((r for r in sim_single if r.team_id != winner.team_id), key=lambda r: r.final_count)
    print(f"  Champion:    {winner.team_name}")
    print(f"  Runner-up:   {runner_up.team_name}")
    print(f"  Semi-finalists:")
    for r in sorted(sim_single, key=lambda x: x.semi_final_count, reverse=True)[:4]:
        print(f"    {r.team_name}")

    ###########################################################################
    # FASE 7.6A - 10k, 50k, 100k simulations
    ###########################################################################
    all_sim_data = {}

    for n_sims, label in [(10_000, "10k"), (50_000, "50k"), (100_000, "100k")]:
        print(f"\n{'-' * 65}")
        results, duration, strengths, _ = run_simulation_batch(
            teams, group_mapping, n_sims, parallel=False, label=f"({label})"
        )
        champ_probs, final_probs, semi_probs, qual_probs, anomalies = analyze_simulation(
            results, teams, n_sims, label
        )
        all_sim_data[label] = {
            "results": results,
            "champion_probs": champ_probs,
            "finalist_probs": final_probs,
            "semi_probs": semi_probs,
            "qual_probs": qual_probs,
            "anomalies": anomalies,
            "duration": duration,
        }

        # Print top 10 champions
        print(f"\n  Top 10 Champions ({label}):")
        print(f"  {'Team':25s} {'Prob':>8s} {'Group':>6s}")
        print(f"  {'-'*39}")
        for name, pct, group in champ_probs[:10]:
            print(f"  {name:25s} {pct:7.3f}% {group:>6s}")

        print(f"\n  {'Top 10 Finalists':30s} {'Prob':>8s} {'Group':>6s}")
        print(f"  {'-'*44}")
        for name, pct, group in final_probs[:10]:
            print(f"  {name:25s} {pct:7.3f}% {group:>6s}")

        # Qualification probabilities for all teams
        print(f"\n  Group Qualification (all teams):")
        print(f"  {'Team':25s} {'R32%':>8s} {'Group':>6s} {'Win%':>8s}")
        print(f"  {'-'*47}")
        for name, data in sorted(qual_probs.items(), key=lambda x: -x[1]["r32_pct"]):
            print(f"  {name:25s} {data['r32_pct']:7.1f}% {data['group']:>6s} {data['win_pct']:7.3f}%")

        if anomalies:
            print(f"\n  Anomalies ({len(anomalies)}):")
            for a in anomalies:
                print(f"    ! {a}")

    ###########################################################################
    # FASE 7.6D - Monte Carlo Convergence
    ###########################################################################
    conv_results = validate_convergence(
        all_sim_data["10k"]["champion_probs"],
        all_sim_data["50k"]["champion_probs"],
        all_sim_data["100k"]["champion_probs"],
    )

    ###########################################################################
    # FASE 7.6E - Calibration
    ###########################################################################
    cal_results = validate_calibration()

    ###########################################################################
    # FASE 7.6F - Performance
    ###########################################################################
    perf_results = validate_performance()

    ###########################################################################
    # Summary
    ###########################################################################
    print("\n" + "=" * 65)
    print("  VALIDATION SUMMARY")
    print("=" * 65)

    total_anomalies = len(match_anomalies)
    for label in ["10k", "50k", "100k"]:
        total_anomalies += len(all_sim_data[label]["anomalies"])

    print(f"\n  Match prediction anomalies:      {len(match_anomalies)}")
    print(f"  Simulation anomalies:            {total_anomalies - len(match_anomalies)}")
    print(f"  Total anomalies:                 {total_anomalies}")
    print(f"  Convergence (avg Delta 10k->100k):   {conv_results['avg_delta']:.3f}%")
    print(f"  Calibration accuracy:            {cal_results['accuracy']*100:.2f}%")
    print(f"  Calibration Brier score:         {cal_results['brier_score']:.4f}")

    ###########################################################################
    # Export data for report generation
    ###########################################################################
    export = {
        "match_results": match_results,
        "match_anomalies": match_anomalies,
        "champion_top20_10k": [(n, round(p, 2), g) for n, p, g in all_sim_data["10k"]["champion_probs"][:20]],
        "champion_top20_50k": [(n, round(p, 2), g) for n, p, g in all_sim_data["50k"]["champion_probs"][:20]],
        "champion_top20_100k": [(n, round(p, 2), g) for n, p, g in all_sim_data["100k"]["champion_probs"][:20]],
        "finalist_top20_10k": [(n, round(p, 2), g) for n, p, g in all_sim_data["10k"]["finalist_probs"][:20]],
        "finalist_top20_50k": [(n, round(p, 2), g) for n, p, g in all_sim_data["50k"]["finalist_probs"][:20]],
        "finalist_top20_100k": [(n, round(p, 2), g) for n, p, g in all_sim_data["100k"]["finalist_probs"][:20]],
        "semi_top20_100k": [(n, round(p, 2), g) for n, p, g in all_sim_data["100k"]["semi_probs"][:20]],
        "qual_probs_100k": {k: {sk: sv for sk, sv in v.items() if sk != "group"} for k, v in all_sim_data["100k"]["qual_probs"].items()},
        "sim_durations": {k: round(all_sim_data[k]["duration"], 2) for k in ["10k", "50k", "100k"]},
        "convergence": conv_results,
        "calibration": cal_results,
        "performance": perf_results,
    }
    export_path = Path(__file__).resolve().parent / "phase76_export.json"
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Export saved to {export_path}")

    print("\n" + "=" * 65)
    print("  VALIDATION COMPLETE")
    print("=" * 65)

    return export


if __name__ == "__main__":
    main()
