"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import { getWinColor } from "@/lib/utils";
import { FlaskConical, Plus, Trash2, Play, AlertTriangle } from "lucide-react";

interface Modification {
  team_name: string;
  result_modifier: number;
  description: string;
}

interface ScenarioResult {
  team_name: string;
  win_prob: number;
  final_prob: number;
  sf_prob: number;
  qf_prob: number;
  r32_prob: number;
  avg_group_points: number;
}

export default function ScenariosPage() {
  const [teams, setTeams] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [modifications, setModifications] = useState<Modification[]>([
    { team_name: "", result_modifier: 10, description: "" },
  ]);
  const [baseline, setBaseline] = useState<any>(null);
  const [results, setResults] = useState<ScenarioResult[] | null>(null);
  const [numScenarios, setNumScenarios] = useState(1000);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.teams.list(1, 100),
    ])
      .then(([t]) => {
        setTeams(t);
        if (t.length) {
          setModifications([{ team_name: t[0].name, result_modifier: 10, description: "" }]);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (baseline) return;
    api.simulations.list().then((sims) => {
      const completed = sims.filter((s) => s.status === "completed");
      if (completed.length) {
        api.simulations.probabilities(completed[0].id).then((data) => setBaseline(data)).catch(() => {});
      }
    }).catch(() => {});
  }, [baseline]);

  const addModification = () => {
    setModifications([...modifications, { team_name: teams[0]?.name || "", result_modifier: 10, description: "" }]);
  };

  const updateMod = (index: number, field: keyof Modification, value: any) => {
    const updated = [...modifications];
    (updated[index] as any)[field] = value;
    setModifications(updated);
  };

  const removeMod = (index: number) => {
    setModifications(modifications.filter((_, i) => i !== index));
  };

  const runScenario = async () => {
    const valid = modifications.filter((m) => m.team_name && m.result_modifier !== 0);
    if (!valid.length) {
      setError("Add at least one modification");
      return;
    }
    setError("");
    setRunning(true);
    try {
      const data = await api.scenarios.simulate({
        modifications: valid.map((m) => ({
          team_name: m.team_name,
          result_modifier: m.result_modifier,
          description: m.description,
        })),
        num_scenarios: numScenarios,
      });
      setResults(data.results);
    } catch (e: any) {
      setError(e.message || "Failed to run scenario");
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <SkeletonPage />;

  return (
    <div className="container-page">
      <div className="flex items-center gap-3 mb-6">
        <FlaskConical className="w-6 h-6 text-primary-600" />
        <div>
          <h1 className="page-title">What-If Analysis</h1>
          <p className="page-subtitle">Modify team strengths and see how tournament probabilities change.</p>
        </div>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Scenario Modifications
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {modifications.map((mod, i) => (
            <div key={i} className="flex items-center gap-3 flex-wrap">
              <select
                value={mod.team_name}
                onChange={(e) => updateMod(i, "team_name", e.target.value)}
                className="flex-1 min-w-[140px] px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
              >
                {teams.map((t: any) => (
                  <option key={t.id} value={t.name}>{t.name}</option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500 whitespace-nowrap">Strength:</label>
                <input
                  type="number"
                  value={mod.result_modifier}
                  onChange={(e) => updateMod(i, "result_modifier", Number(e.target.value))}
                  className="w-20 px-2 py-1.5 border border-gray-200 rounded-lg text-sm text-right"
                  step="5"
                />
                <span className="text-xs text-gray-400">%</span>
              </div>
              <input
                type="text"
                placeholder="Label (optional)"
                value={mod.description}
                onChange={(e) => updateMod(i, "description", e.target.value)}
                className="flex-1 min-w-[120px] px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
              />
              {modifications.length > 1 && (
                <button onClick={() => removeMod(i)} className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
          <div className="flex items-center gap-3 pt-2">
            <button onClick={addModification} className="flex items-center gap-1 px-3 py-1.5 text-sm text-primary-600 hover:bg-primary-50 rounded-lg transition-colors">
              <Plus className="w-4 h-4" /> Add Team
            </button>
            <div className="flex items-center gap-2 ml-auto">
              <label className="text-xs text-gray-500">Simulations:</label>
              <input
                type="number"
                value={numScenarios}
                onChange={(e) => setNumScenarios(Math.max(100, Math.min(10000, Number(e.target.value))))}
                className="w-24 px-2 py-1.5 border border-gray-200 rounded-lg text-sm text-right"
                min={100}
                max={10000}
                step={100}
              />
            </div>
            <button
              onClick={runScenario}
              disabled={running}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              <Play className="w-4 h-4" />
              {running ? "Running..." : "Run Scenario"}
            </button>
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
        </CardContent>
      </Card>

      {results && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-primary-600" />
              Scenario Results
              <span className="text-xs text-gray-400 font-normal ml-2">
                ({numScenarios.toLocaleString()} simulations)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 pr-4 font-medium text-gray-500">Team</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">R32</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">QF</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">SF</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Final</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-500">Win</th>
                    {baseline && <th className="text-right py-2 px-2 font-medium text-gray-500">Δ Win</th>}
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 30).map((r) => {
                    const baseTeam = baseline?.teams?.find((t: any) => t.team_name === r.team_name);
                    const delta = baseTeam ? r.win_prob - baseTeam.win_prob : null;
                    return (
                      <tr key={r.team_name} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4 font-medium">{r.team_name}</td>
                        <td className={`py-2 px-2 text-right ${getWinColor(r.r32_prob)}`}>{r.r32_prob}%</td>
                        <td className={`py-2 px-2 text-right ${getWinColor(r.qf_prob)}`}>{r.qf_prob}%</td>
                        <td className={`py-2 px-2 text-right ${getWinColor(r.sf_prob)}`}>{r.sf_prob}%</td>
                        <td className={`py-2 px-2 text-right ${getWinColor(r.final_prob)}`}>{r.final_prob}%</td>
                        <td className={`py-2 px-2 text-right ${getWinColor(r.win_prob)}`}>{r.win_prob}%</td>
                        {baseline && (
                          <td                           className={`py-2 px-2 text-right font-semibold ${
                            delta != null && delta > 0 ? "text-green-600" : delta != null && delta < 0 ? "text-red-500" : "text-gray-400"
                          }`}>
                            {delta != null ? `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%` : "—"}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {!results && !loading && (
        <div className="text-center py-16 text-gray-400">
          <FlaskConical className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Add modifications to team strengths and run a scenario simulation.</p>
          <p className="text-xs mt-2">Example: Increase Brazil strength by 10% and see how win probability changes.</p>
        </div>
      )}
    </div>
  );
}
