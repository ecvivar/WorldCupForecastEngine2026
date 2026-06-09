const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ---- Domain Types ----

export interface Team {
  id: string;
  name: string;
  fifa_code: string | null;
  flag_url: string | null;
  continent: string | null;
  founded_year: number | null;
  is_national_team: boolean;
}

export interface Match {
  id: string;
  competition_id: string;
  home_team_id: string;
  away_team_id: string;
  match_date: string;
  stage: string;
  group_name: string | null;
  home_goals: number | null;
  away_goals: number | null;
  home_xg: number | null;
  away_xg: number | null;
  is_neutral_venue: boolean;
  status: string;
}

export interface GroupStanding {
  id: string;
  group_id: string;
  team_id: string;
  team_name: string;
  position: number;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  qualified: boolean;
}

export interface GroupDetail {
  id: string;
  competition_id: string;
  name: string;
  stage: string;
  standings: GroupStanding[];
}

export interface IGFScore {
  team_id: string;
  team_name: string;
  igf_score: number;
  components: Record<string, number>;
}

export interface Simulation {
  id: string;
  competition_id: string;
  name: string | null;
  num_simulations: number;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface SimulationResult {
  id: string;
  team_id: string;
  team_name: string;
  group_name: string | null;
  group_position: number | null;
  reached_round_of_32: number;
  reached_round_of_16: number;
  reached_quarter_final: number;
  reached_semi_final: number;
  reached_final: number;
  won_tournament: number;
  points: number;
}

export interface SimulationDetail extends Simulation {
  results: SimulationResult[];
}

export interface MatchPrediction {
  match_id: string;
  home_team: string;
  away_team: string;
  home_win_prob: number;
  draw_prob: number;
  away_win_prob: number;
  home_expected_goals: number;
  away_expected_goals: number;
  most_likely_score: string;
  score_probabilities: Record<string, number> | null;
}

export interface FullMatchPrediction extends MatchPrediction {
  stage?: string;
  group_name?: string;
  match_date?: string;
  top_10_scores: [string, number][];
  confidence_index: number;
  confidence_level: string;
  surprise_risk: number;
  btts_prob: number;
  over_25_prob: number;
  under_25_prob: number;
  over_35_prob: number;
  home_clean_sheet: number;
  away_clean_sheet: number;
}

// ---- Dashboard Types ----

export interface DashboardTeam {
  rank: number;
  team_name: string;
  fifa_code: string | null;
  continent: string | null;
  igf_score: number;
  elo_score: number;
}

export interface DashboardSimulation {
  id: string;
  name: string | null;
  num_simulations: number;
  completed_at: string | null;
}

export interface WinnerProb {
  team_name: string;
  fifa_code: string | null;
  win_prob: number;
  final_prob: number;
  sf_prob: number;
  qf_prob: number;
}

export interface DashboardPrediction {
  match_id: string;
  stage: string;
  match_date: string | null;
  home_team: string;
  away_team: string;
  home_win_prob: number;
  draw_prob: number;
  away_win_prob: number;
  most_likely_score: string | null;
  confidence_index: number | null;
  confidence_level: string | null;
  surprise_risk: number | null;
}

export interface DashboardGroupTeam {
  team_name: string;
  fifa_code: string | null;
  position: number;
  points: number;
  goal_difference: number;
  qualified: boolean;
}

export interface DashboardGroup {
  name: string;
  teams: DashboardGroupTeam[];
}

export interface DashboardData {
  total_teams: number;
  total_matches: number;
  total_groups: number;
  group_matches: number;
  knockout_matches: number;
  top_teams: DashboardTeam[];
  simulation: DashboardSimulation | null;
  winner_probs: WinnerProb[];
  recent_predictions: DashboardPrediction[];
  groups: DashboardGroup[];
}

// ---- Simulation Probability Types ----

export interface TeamStageProb {
  team_name: string;
  fifa_code: string | null;
  continent: string | null;
  group_name: string;
  group_position: number | null;
  qualify_r32_prob: number;
  r16_prob: number;
  qf_prob: number;
  sf_prob: number;
  final_prob: number;
  win_prob: number;
  avg_points: number;
}

export interface GroupProb {
  team_name: string;
  fifa_code: string | null;
  qualify_r32_prob: number;
  avg_points: number;
}

export interface SimulationProbabilities {
  simulation_id: string;
  num_simulations: number;
  teams: TeamStageProb[];
  groups: Record<string, GroupProb[]>;
}

// ---- Calibration Types ----

export interface CalibrationMetric {
  brier_score: number;
  log_loss: number;
  accuracy: number;
  calibration_error: number;
  auc_roc: number;
}

export interface CalibrationBin {
  bin_lower: number;
  bin_upper: number;
  count: number;
  mean_predicted: number;
  mean_actual: number;
}

export interface OutcomeCurve {
  outcome: string;
  bins: CalibrationBin[];
}

export interface ConfederationBias {
  confederation: string;
  match_count: number;
  brier_score: number;
  accuracy: number;
  home_win_pred: number;
  home_win_actual: number;
  favorite_pred: number;
  favorite_actual: number;
  draw_pred: number;
  draw_actual: number;
}

export interface BenchmarkModel {
  model_name: string;
  overall: CalibrationMetric;
  improvement_vs_baseline: number;
}

export interface CalibrationReport {
  overall: CalibrationMetric;
  by_tournament: Record<string, CalibrationMetric>;
  by_stage: Record<string, CalibrationMetric>;
  calibration_curve: CalibrationBin[];
  outcome_curves: OutcomeCurve[];
  bias: Record<string, number>;
  confederation_biases: ConfederationBias[];
  match_count: number;
}

// ---- Calibration Refinement Types ----

export interface ReliabilityBucket {
  bucket_label: string;
  lower: number;
  upper: number;
  count: number;
  mean_predicted: number;
  observed_frequency: number;
  absolute_error: number;
  relative_error: number;
}

export interface ReliabilityCurve {
  outcome: string;
  buckets: ReliabilityBucket[];
}

export interface CalibrationMethod {
  method_name: string;
  brier_score: number;
  log_loss: number;
  accuracy: number;
  ece: number;
  parameters: Record<string, unknown>;
}

export interface BiasReduction {
  adjustment_name: string;
  before_metric: number;
  after_metric: number;
  improvement: number;
  applied: boolean;
}

export interface BenchmarkEntry {
  brier_score: number;
  log_loss: number;
  accuracy: number;
  ece: number;
}

export interface RefinementReport {
  reliability_curves: ReliabilityCurve[];
  calibration_methods: CalibrationMethod[];
  best_method: string;
  benchmark_before: Record<string, BenchmarkEntry>;
  benchmark_after: Record<string, BenchmarkEntry>;
  bias_reductions: BiasReduction[];
  recommendation: string;
}

// ---- Group Analysis / Power Ranking ----

export interface PowerRankingTeam {
  team_name: string;
  fifa_code: string | null;
  continent: string | null;
  elo_score: number;
  fifa_rank: number;
  igf_score: number;
  rank: number;
}

export interface PowerRanking {
  title_contenders: PowerRankingTeam[];
  semi_final_candidates: PowerRankingTeam[];
  quarter_final_candidates: PowerRankingTeam[];
  early_exit_candidates: PowerRankingTeam[];
}

// ---- API Methods ----

export const api = {
  teams: {
    list: (page = 1, perPage = 20) =>
      fetchJSON<Team[]>(`/teams?page=${page}&per_page=${perPage}`),
    get: (id: string) => fetchJSON<Team>(`/teams/${id}`),
  },
  matches: {
    list: (page = 1, perPage = 20, stage?: string) => {
      let path = `/matches?page=${page}&per_page=${perPage}`;
      if (stage) path += `&stage=${stage}`;
      return fetchJSON<Match[]>(path);
    },
    get: (id: string) => fetchJSON<Match>(`/matches/${id}`),
    predict: (id: string) =>
      fetchJSON<FullMatchPrediction>(`/matches/${id}/prediction`),
  },
  groups: {
    list: () => fetchJSON<GroupDetail[]>("/groups"),
    get: (id: string) => fetchJSON<GroupDetail>(`/groups/${id}`),
    analysis: (id: string) => fetchJSON<any>(`/groups/${id}/analysis`),
  },
  rankings: {
    elo: () => fetchJSON<any[]>("/rankings/elo"),
    fifa: () => fetchJSON<any[]>("/rankings/fifa"),
    igf: () => fetchJSON<IGFScore[]>("/rankings/igf"),
    powerRanking: () => fetchJSON<PowerRanking>("/rankings/power-ranking"),
  },
  predictions: {
    list: () => fetchJSON<MatchPrediction[]>("/predictions"),
    rankings: () => fetchJSON<IGFScore[]>("/predictions/rankings"),
    full: (matchId: string) =>
      fetchJSON<FullMatchPrediction>(`/predictions/full/${matchId}`),
    betting: (matchId: string) =>
      fetchJSON<any>(`/predictions/betting/${matchId}`),
  },
  simulations: {
    list: () => fetchJSON<Simulation[]>("/simulations"),
    get: (id: string) => fetchJSON<SimulationDetail>(`/simulations/${id}`),
    create: (data: { competition_id: string; num_simulations: number }) =>
      fetchJSON<Simulation>("/simulations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    run: (id: string) =>
      fetchJSON<SimulationDetail>(`/simulations/${id}/run`, {
        method: "POST",
      }),
    probabilities: (id: string) =>
      fetchJSON<SimulationProbabilities>(`/simulations/${id}/probabilities`),
  },
  dashboard: {
    get: () => fetchJSON<DashboardData>("/dashboard"),
  },
  calendar: {
    get: () => fetchJSON<any[]>("/matches/calendar"),
  },
  calibration: {
    run: (modelType = "full") =>
      fetchJSON<CalibrationReport>(`/calibration/run?model_type=${modelType}`, {
        method: "POST",
      }),
    benchmark: () =>
      fetchJSON<CalibrationReport>("/calibration/benchmark", {
        method: "POST",
      }),
    results: () => fetchJSON<CalibrationReport>("/calibration/results"),
    apply: (adjustments: Record<string, number>) =>
      fetchJSON<any>("/calibration/apply", {
        method: "POST",
        body: JSON.stringify({ adjustments }),
      }),
    adjustments: () => fetchJSON<any>("/calibration/adjustments"),
  },
  refinement: {
    run: () =>
      fetchJSON<RefinementReport>("/calibration/refinement/run", {
        method: "POST",
      }),
    results: () =>
      fetchJSON<RefinementReport>("/calibration/refinement/results"),
  },
  comparison: {
    compare: (teamAId: string, teamBId: string) =>
      fetchJSON<any>(`/comparison/teams/${teamAId}/${teamBId}`),
  },
  scenarios: {
    simulate: (data: {
      modifications: { team_name: string; result_modifier: number; description?: string }[];
      num_scenarios: number;
    }) =>
      fetchJSON<any>("/scenarios/simulate", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
};
