"use client";

import { useEffect, useState } from "react";
import { api, IGFScore } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import TeamRadarChart from "@/components/TeamRadarChart";
import ProbabilityBar from "@/components/ProbabilityBar";
import { getContinentColor, getConfidenceColor, getConfidenceLabel } from "@/lib/utils";
import { Scale, ArrowRight, Trophy, Target, Swords } from "lucide-react";

interface ComparisonData {
  team_a: any;
  team_b: any;
  head_to_head_prediction: any;
}

export default function ComparisonPage() {
  const [teams, setTeams] = useState<any[]>([]);
  const [igfScores, setIgfScores] = useState<IGFScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    Promise.all([
      api.teams.list(1, 100),
      api.rankings.igf().catch(() => []),
    ])
      .then(([t, igf]) => {
        setTeams(t);
        setIgfScores(igf);
        if (t.length >= 2) {
          setTeamA(t[0].id);
          setTeamB(t[1].id);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const igfMap = new Map(igfScores.map((s) => [s.team_name, s]));

  const handleCompare = async () => {
    if (!teamA || !teamB) return;
    setComparing(true);
    try {
      const data = await api.comparison.compare(teamA, teamB);
      setComparison(data);
    } catch (e) {
      console.error(e);
    } finally {
      setComparing(false);
    }
  };

  if (loading) return <SkeletonPage />;

  const StatRow = ({ label, a, b, fmt = (v: any) => v, unit = "" }: { label: string; a: any; b: any; fmt?: (v: any) => any; unit?: string }) => (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-500 w-1/3">{label}</span>
      <span className="text-sm font-semibold text-right w-1/3">{fmt(a)}{unit}</span>
      <span className="text-xs text-gray-400 w-8 text-center">
        {a != null && b != null ? (
          a > b ? "▲" : a < b ? "▼" : "—"
        ) : "—"}
      </span>
      <span className="text-sm font-semibold text-right w-1/3">{fmt(b)}{unit}</span>
    </div>
  );

  return (
    <div className="container-page">
      <div className="flex items-center gap-3 mb-6">
        <Scale className="w-6 h-6 text-primary-600" />
        <div>
          <h1 className="page-title">Team Comparison</h1>
          <p className="page-subtitle">Compare two teams head-to-head across all metrics.</p>
        </div>
      </div>

      <Card className="mb-8">
        <CardContent className="pt-6">
          <div className="flex items-end gap-4 flex-wrap">
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-500 mb-1">Team A</label>
              <select
                value={teamA}
                onChange={(e) => setTeamA(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center pb-2">
              <Swords className="w-5 h-5 text-gray-400" />
            </div>
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-500 mb-1">Team B</label>
              <select
                value={teamB}
                onChange={(e) => setTeamB(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleCompare}
              disabled={comparing || teamA === teamB}
              className="px-5 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {comparing ? "Comparing..." : "Compare"}
            </button>
          </div>
        </CardContent>
      </Card>

      {comparison && (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="border-2 border-blue-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-blue-700">
                  <Trophy className="w-5 h-5" /> {comparison.team_a.team_name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1 mb-4">
                  <Badge className={getContinentColor(comparison.team_a.continent)}>
                    {comparison.team_a.continent || "Unknown"}
                  </Badge>
                  {comparison.team_a.fifa_code && (
                    <span className="text-xs text-gray-400 ml-2">FIFA: {comparison.team_a.fifa_code}</span>
                  )}
                </div>
                <TeamRadarChart
                  teamName={comparison.team_a.team_name}
                  components={igfMap.get(comparison.team_a.team_name)?.components || {}}
                />
              </CardContent>
            </Card>

            <Card className="border-2 border-red-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-red-700">
                  <Target className="w-5 h-5" /> {comparison.team_b.team_name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1 mb-4">
                  <Badge className={getContinentColor(comparison.team_b.continent)}>
                    {comparison.team_b.continent || "Unknown"}
                  </Badge>
                  {comparison.team_b.fifa_code && (
                    <span className="text-xs text-gray-400 ml-2">FIFA: {comparison.team_b.fifa_code}</span>
                  )}
                </div>
                <TeamRadarChart
                  teamName={comparison.team_b.team_name}
                  components={igfMap.get(comparison.team_b.team_name)?.components || {}}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Head-to-Head Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between mb-4 text-sm font-semibold text-gray-700 pb-2 border-b border-gray-200">
                <span className="w-1/3 text-blue-600">{comparison.team_a.team_name}</span>
                <span className="w-8 text-center text-gray-400 text-xs">VS</span>
                <span className="w-1/3 text-red-600 text-right">{comparison.team_b.team_name}</span>
              </div>
              <StatRow label="Elo Score" a={comparison.team_a.elo_score} b={comparison.team_b.elo_score} fmt={Math.round} />
              <StatRow label="IGF Score" a={comparison.team_a.igf_score} b={comparison.team_b.igf_score} fmt={(v: number) => v.toFixed(1)} />
              <StatRow label="FIFA Rank" a={comparison.team_a.fifa_rank} b={comparison.team_b.fifa_rank} fmt={(v: any) => v ?? "—"} />
              <StatRow label="Group" a={comparison.team_a.group_name} b={comparison.team_b.group_name} fmt={(v: any) => v ?? "—"} />
              <StatRow label="Group Position" a={comparison.team_a.group_position} b={comparison.team_b.group_position} fmt={(v: any) => v ?? "—"} />
              <StatRow label="Group Points" a={comparison.team_a.group_points} b={comparison.team_b.group_points} fmt={(v: any) => v ?? "—"} />
              {comparison.team_a.xg_for != null && (
                <StatRow label="xG For" a={comparison.team_a.xg_for} b={comparison.team_b.xg_for} fmt={(v: number) => v.toFixed(2)} />
              )}
              {comparison.team_a.xg_against != null && (
                <StatRow label="xG Against" a={comparison.team_a.xg_against} b={comparison.team_b.xg_against} fmt={(v: number) => v.toFixed(2)} />
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            {comparison.team_a.simulation && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{comparison.team_a.team_name} — Tournament Outlook</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">Win Tournament</span><span className="font-semibold text-green-600">{comparison.team_a.simulation.win_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Final</span><span className="font-semibold">{comparison.team_a.simulation.final_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Semi-Final</span><span className="font-semibold">{comparison.team_a.simulation.sf_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Quarter-Final</span><span className="font-semibold">{comparison.team_a.simulation.qf_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Avg Group Points</span><span className="font-semibold">{comparison.team_a.simulation.avg_points}</span></div>
                </CardContent>
              </Card>
            )}
            {comparison.team_b.simulation && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{comparison.team_b.team_name} — Tournament Outlook</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">Win Tournament</span><span className="font-semibold text-green-600">{comparison.team_b.simulation.win_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Final</span><span className="font-semibold">{comparison.team_b.simulation.final_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Semi-Final</span><span className="font-semibold">{comparison.team_b.simulation.sf_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Reach Quarter-Final</span><span className="font-semibold">{comparison.team_b.simulation.qf_prob}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Avg Group Points</span><span className="font-semibold">{comparison.team_b.simulation.avg_points}</span></div>
                </CardContent>
              </Card>
            )}
          </div>

          {comparison.head_to_head_prediction && (
            <Card className="border-2 border-primary-200">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <ArrowRight className="w-5 h-5 text-primary-600" />
                  Head-to-Head Prediction
                  {comparison.head_to_head_prediction.confidence_index != null && (
                    <Badge className={getConfidenceColor(comparison.head_to_head_prediction.confidence_index)}>
                      {getConfidenceLabel(comparison.head_to_head_prediction.confidence_index)}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <ProbabilityBar
                  homeWin={comparison.head_to_head_prediction.home_win_prob}
                  draw={comparison.head_to_head_prediction.draw_prob}
                  awayWin={comparison.head_to_head_prediction.away_win_prob}
                  homeLabel={comparison.team_a.team_name}
                  awayLabel={comparison.team_b.team_name}
                />
                <div className="grid grid-cols-3 gap-4 text-center text-sm">
                  <div>
                    <div className="text-blue-600 font-bold text-lg">{comparison.head_to_head_prediction.home_win_prob.toFixed(1)}%</div>
                    <div className="text-gray-500 text-xs">Home Win</div>
                  </div>
                  <div>
                    <div className="text-gray-600 font-bold text-lg">{comparison.head_to_head_prediction.draw_prob.toFixed(1)}%</div>
                    <div className="text-gray-500 text-xs">Draw</div>
                  </div>
                  <div>
                    <div className="text-red-600 font-bold text-lg">{comparison.head_to_head_prediction.away_win_prob.toFixed(1)}%</div>
                    <div className="text-gray-500 text-xs">Away Win</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-gray-500 text-xs">Most Likely Score</div>
                    <div className="font-semibold">{comparison.head_to_head_prediction.most_likely_score}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-gray-500 text-xs">BTTS</div>
                    <div className="font-semibold">{(comparison.head_to_head_prediction.btts_prob * 100).toFixed(0)}%</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-gray-500 text-xs">Over 2.5</div>
                    <div className="font-semibold">{(comparison.head_to_head_prediction.over_25_prob * 100).toFixed(0)}%</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className="text-gray-500 text-xs">Surprise Risk</div>
                    <div className="font-semibold">{(comparison.head_to_head_prediction.surprise_risk * 100).toFixed(0)}%</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!comparison && !loading && (
        <div className="text-center py-16 text-gray-400">
          <Swords className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Select two teams and click Compare to see head-to-head analysis.</p>
        </div>
      )}
    </div>
  );
}
