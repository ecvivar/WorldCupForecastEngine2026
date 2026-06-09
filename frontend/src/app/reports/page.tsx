"use client";

import { useEffect, useState } from "react";
import { api, DashboardData, SimulationProbabilities, IGFScore, PowerRanking } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import { getContinentColor, getWinColor } from "@/lib/utils";
import TeamRadarChart from "@/components/TeamRadarChart";
import {
  BarChart3, TrendingUp, Award, Lightbulb, ChevronRight,
  Crown, Star, Zap, AlertTriangle,
} from "lucide-react";

interface ReportSection {
  title: string;
  icon: any;
  content: React.ReactNode;
}

export default function ReportsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [igfScores, setIgfScores] = useState<IGFScore[]>([]);
  const [powerRanking, setPowerRanking] = useState<PowerRanking | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.dashboard.get().catch(() => null),
      api.rankings.igf().catch(() => []),
      api.rankings.powerRanking().catch(() => null),
    ])
      .then(([d, igf, pr]) => {
        setDashboard(d);
        setIgfScores(igf);
        setPowerRanking(pr);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonPage />;

  const topContenders = dashboard?.winner_probs?.slice(0, 5) || [];
  const darkHorses = igfScores
    .filter((s) => {
      const inTop5 = topContenders.some((c) => c.team_name === s.team_name);
      return !inTop5 && s.igf_score > 50;
    })
    .sort((a, b) => b.igf_score - a.igf_score)
    .slice(0, 5);

  const sortedTeams = [...(dashboard?.top_teams || [])].sort((a, b) => b.igf_score - a.igf_score);

  return (
    <div className="container-page">
      <div className="flex items-center gap-3 mb-6">
        <BarChart3 className="w-6 h-6 text-primary-600" />
        <div>
          <h1 className="page-title">Reporting Dashboard</h1>
          <p className="page-subtitle">Executive summary of tournament insights, contenders, and forecasts.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-gray-500 font-normal flex items-center gap-1">
              <Award className="w-3 h-3" /> Top Contenders
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary-600">{topContenders.length}</div>
            <div className="text-xs text-gray-400">Teams with highest champion probability</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-gray-500 font-normal flex items-center gap-1">
              <Star className="w-3 h-3" /> Dark Horses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{darkHorses.length}</div>
            <div className="text-xs text-gray-400">Teams with high IGF outside top 5 favorites</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-gray-500 font-normal flex items-center gap-1">
              <Zap className="w-3 h-3" /> Most Likely Final
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm font-semibold truncate">
              {topContenders[0]?.team_name || "—"} vs {topContenders[1]?.team_name || "—"}
            </div>
            <div className="text-xs text-gray-400">
              {topContenders[0] ? `${topContenders[0].win_prob}% vs ${topContenders[1]?.win_prob || 0}%` : ""}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-gray-500 font-normal flex items-center gap-1">
              <Lightbulb className="w-3 h-3" /> Tournament Insight
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm font-semibold">
              {dashboard?.total_teams || 0} Teams
            </div>
            <div className="text-xs text-gray-400">
              {dashboard?.total_matches || 0} matches across {dashboard?.total_groups || 0} groups
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Crown className="w-4 h-4 text-amber-500" />
              Top Contenders
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topContenders.map((t, i) => (
                <div key={t.team_name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? "bg-amber-100 text-amber-700" :
                      i === 1 ? "bg-gray-200 text-gray-600" :
                      i === 2 ? "bg-orange-100 text-orange-700" :
                      "bg-gray-100 text-gray-500"
                    }`}>{i + 1}</span>
                    <span className="text-sm font-medium">{t.team_name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-gray-400">{t.qf_prob}% QF</span>
                    <span className="text-gray-400">{t.sf_prob}% SF</span>
                    <span className={`font-semibold ${getWinColor(t.win_prob)}`}>{t.win_prob}% Win</span>
                  </div>
                </div>
              ))}
              {!topContenders.length && <p className="text-sm text-gray-400">No simulation data available.</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-500" />
              Dark Horses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {darkHorses.map((t) => (
                <div key={t.team_name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs">★</span>
                    <span className="text-sm font-medium">{t.team_name}</span>
                  </div>
                  <span className="text-xs font-semibold text-amber-600">IGF {t.igf_score.toFixed(1)}</span>
                </div>
              ))}
              {!darkHorses.length && <p className="text-sm text-gray-400">No dark horses identified.</p>}
            </div>
          </CardContent>
        </Card>

        {powerRanking && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Crown className="w-4 h-4 text-green-600" />
                  Title Contenders
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {powerRanking.title_contenders?.slice(0, 8).map((t, i) => (
                    <div key={t.team_name} className="flex items-center justify-between text-sm">
                      <span>{i + 1}. {t.team_name}</span>
                      <span className="text-xs text-gray-500">IGF {t.igf_score.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  Early Exit Candidates
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {powerRanking.early_exit_candidates?.slice(0, 8).map((t, i) => (
                    <div key={t.team_name} className="flex items-center justify-between text-sm">
                      <span>{i + 1}. {t.team_name}</span>
                      <span className="text-xs text-gray-500">IGF {t.igf_score.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {sortedTeams.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              IGF Score Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {sortedTeams.slice(0, 20).map((t, i) => (
                <div key={t.team_name} className="flex items-center gap-3 text-sm">
                  <span className="w-6 text-right text-xs text-gray-400">{i + 1}.</span>
                  <span className="w-32 truncate font-medium">{t.team_name}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-primary-500 h-2 rounded-full"
                      style={{ width: `${Math.min(t.igf_score, 100)}%` }}
                    />
                  </div>
                  <span className="w-12 text-right text-xs font-semibold text-gray-600">{t.igf_score.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-500" />
            Key Insights
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {topContenders[0] && (
              <div className="p-3 bg-blue-50 rounded-lg text-sm">
                <span className="font-semibold text-blue-700">Favorite: </span>
                <span className="text-blue-600">{topContenders[0].team_name} has a {topContenders[0].win_prob}% chance to win the World Cup.</span>
              </div>
            )}
            {darkHorses[0] && (
              <div className="p-3 bg-amber-50 rounded-lg text-sm">
                <span className="font-semibold text-amber-700">Dark Horse: </span>
                <span className="text-amber-600">{darkHorses[0].team_name} (IGF: {darkHorses[0].igf_score.toFixed(1)}) could surprise.</span>
              </div>
            )}
            {topContenders[1] && (
              <div className="p-3 bg-green-50 rounded-lg text-sm">
                <span className="font-semibold text-green-700">Most Likely Final: </span>
                <span className="text-green-600">{topContenders[0].team_name} vs {topContenders[1].team_name}</span>
              </div>
            )}
            {topContenders.length > 2 && (
              <div className="p-3 bg-purple-50 rounded-lg text-sm">
                <span className="font-semibold text-purple-700">Contender: </span>
                <span className="text-purple-600">{topContenders[2].team_name} has a {topContenders[2].win_prob}% win probability (QF: {topContenders[2].qf_prob}%).</span>
              </div>
            )}
            {dashboard?.total_matches && (
              <div className="p-3 bg-gray-50 rounded-lg text-sm">
                <span className="font-semibold text-gray-700">Tournament Scale: </span>
                <span className="text-gray-600">{dashboard.total_teams} teams, {dashboard.total_matches} matches, {dashboard.total_groups} groups.</span>
              </div>
            )}
            {dashboard?.winner_probs?.length && (
              <div className="p-3 bg-indigo-50 rounded-lg text-sm">
                <span className="font-semibold text-indigo-700">Competition: </span>
                <span className="text-indigo-600">Top 5 teams have {dashboard.winner_probs.slice(0, 5).reduce((s, t) => s + t.win_prob, 0).toFixed(0)}% combined win probability.</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
