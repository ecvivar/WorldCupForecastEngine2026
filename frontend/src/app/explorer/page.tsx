"use client";

import { useEffect, useState } from "react";
import { api, Simulation, SimulationProbabilities, TeamStageProb } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import StageProgressBar from "@/components/StageProgressBar";
import { getContinentColor, getWinColor } from "@/lib/utils";
import { Map as MapIcon, Network, Flag, Footprints } from "lucide-react";

export default function ExplorerPage() {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [probData, setProbData] = useState<SimulationProbabilities | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSim, setSelectedSim] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [view, setView] = useState<"groups" | "knockout" | "team-path">("groups");

  useEffect(() => {
    api.simulations.list()
      .then((s) => {
        setSimulations(s);
        if (s.length) {
          setSelectedSim(s[0].id);
          return api.simulations.probabilities(s[0].id);
        }
        return null;
      })
      .then((data) => {
        if (data) {
          setProbData(data);
          if (data.teams.length) setSelectedTeam(data.teams[0].team_name);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSimChange = (id: string) => {
    setSelectedSim(id);
    setLoading(true);
    api.simulations.probabilities(id)
      .then((data) => {
        setProbData(data);
        if (data.teams.length) setSelectedTeam(data.teams[0].team_name);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  if (loading) return <SkeletonPage />;
  if (!probData) return <div className="container-page"><p className="text-gray-400">No simulation data available. Run a simulation first.</p></div>;

  const tabs = [
    { id: "groups", label: "Group Stage", icon: MapIcon },
    { id: "knockout", label: "Knockout Probabilities", icon: Network },
    { id: "team-path", label: "Team Path", icon: Footprints },
  ] as const;

  const teamProbsMap = new Map(probData.teams.map((t: TeamStageProb) => [t.team_name, t] as const));

  return (
    <div className="container-page">
      <div className="flex items-center gap-3 mb-6">
        <Network className="w-6 h-6 text-primary-600" />
        <div>
          <h1 className="page-title">Tournament Explorer</h1>
          <p className="page-subtitle">Explore group stage, knockout probabilities, and team paths.</p>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Simulation</label>
          <select
            value={selectedSim}
            onChange={(e) => handleSimChange(e.target.value)}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
          >
            {simulations.map((s) => (
              <option key={s.id} value={s.id}>{s.name || s.id.slice(0, 8)} ({s.num_simulations.toLocaleString()} sims)</option>
            ))}
          </select>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                view === tab.id ? "bg-white shadow-sm text-primary-700" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {view === "groups" && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(probData.groups || {}).sort().map(([groupName, teams]) => (
            <Card key={groupName}>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Flag className="w-4 h-4 text-primary-600" />
                  Group {groupName}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {teams.sort((a, b) => b.qualify_r32_prob - a.qualify_r32_prob).map((t, i) => (
                    <div key={t.team_name} className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs text-gray-400 w-4">{i + 1}.</span>
                        <span className="text-sm truncate max-w-[120px]">{t.team_name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-500">{t.avg_points.toFixed(1)} pts</span>
                        <div className="w-20 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-primary-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(t.qualify_r32_prob, 100)}%` }}
                          />
                        </div>
                        <span className={`text-xs w-12 text-right ${getWinColor(t.qualify_r32_prob)}`}>
                          {t.qualify_r32_prob}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {view === "knockout" && (
        <Card>
          <CardHeader>
            <CardTitle>Knockout Stage Probabilities</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 pr-4 font-medium text-gray-500">Team</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Continent</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Group</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">R32</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">R16</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">QF</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">SF</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Final</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Win</th>
                  </tr>
                </thead>
                <tbody>
                  {probData.teams.map((t) => (
                    <tr key={t.team_name} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2 pr-4 font-medium truncate max-w-[140px]">{t.team_name}</td>
                      <td className="py-2 px-2 text-right">
                        <Badge className={getContinentColor(t.continent)}>{t.continent}</Badge>
                      </td>
                      <td className="py-2 px-2 text-right text-gray-500">{t.group_name}</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.qualify_r32_prob)}`}>{t.qualify_r32_prob}%</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.r16_prob)}`}>{t.r16_prob}%</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.qf_prob)}`}>{t.qf_prob}%</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.sf_prob)}`}>{t.sf_prob}%</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.final_prob)}`}>{t.final_prob}%</td>
                      <td className={`py-2 px-2 text-right ${getWinColor(t.win_prob)}`}>{t.win_prob}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {view === "team-path" && (
        <div className="space-y-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <label className="text-sm font-medium text-gray-600">Select Team:</label>
                <select
                  value={selectedTeam}
                  onChange={(e) => setSelectedTeam(e.target.value)}
                  className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
                >
                  {probData.teams.map((t) => (
                    <option key={t.team_name} value={t.team_name}>{t.team_name}</option>
                  ))}
                </select>
              </div>
            </CardContent>
          </Card>

          {selectedTeam && teamProbsMap.has(selectedTeam) && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{selectedTeam} — Stage-by-Stage Probability</CardTitle>
                </CardHeader>
                <CardContent>
                  <StageProgressBar
                    stages={[
                      { label: "Group → R32", prob: teamProbsMap.get(selectedTeam)!.qualify_r32_prob, color: "#3b82f6" },
                      { label: "Round of 16", prob: teamProbsMap.get(selectedTeam)!.r16_prob, color: "#10b981" },
                      { label: "Quarter-Final", prob: teamProbsMap.get(selectedTeam)!.qf_prob, color: "#f59e0b" },
                      { label: "Semi-Final", prob: teamProbsMap.get(selectedTeam)!.sf_prob, color: "#f97316" },
                      { label: "Final", prob: teamProbsMap.get(selectedTeam)!.final_prob, color: "#ef4444" },
                      { label: "Champion", prob: teamProbsMap.get(selectedTeam)!.win_prob, color: "#8b5cf6" },
                    ]}
                  />
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {probData.teams.filter((t) => {
                  const tp = teamProbsMap.get(selectedTeam)!;
                  return t.group_name === tp.group_name && t.team_name !== selectedTeam;
                }).map((opp) => (
                  <Card key={opp.team_name} className="border border-gray-200">
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Flag className="w-4 h-4 text-gray-400" />
                        {opp.team_name}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs space-y-1 text-gray-500">
                      <div className="flex justify-between">
                        <span>Qualify R32</span>
                        <span className="font-semibold">{opp.qualify_r32_prob}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Avg Points</span>
                        <span className="font-semibold">{opp.avg_points.toFixed(1)}</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
