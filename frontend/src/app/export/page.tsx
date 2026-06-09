"use client";

import { useEffect, useState } from "react";
import { api, Simulation, IGFScore } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import { Download, FileJson, FileSpreadsheet, Table, FileText } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const EXPORT_BASE = API_URL;

export default function ExportPage() {
  const [teams, setTeams] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTeam, setSelectedTeam] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedSim, setSelectedSim] = useState("");

  useEffect(() => {
    Promise.all([
      api.teams.list(1, 100),
      api.groups.list().catch(() => []),
      api.simulations.list().catch(() => []),
    ])
      .then(([t, g, s]) => {
        setTeams(t);
        setGroups(g);
        setSimulations(s);
        if (t.length) setSelectedTeam(t[0].id);
        if (g.length) setSelectedGroup(g[0].id);
        if (s.length) setSelectedSim(s[0].id);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonPage />;

  const downloadUrl = (path: string, filename: string) => {
    const a = document.createElement("a");
    a.href = `${EXPORT_BASE}${path}`;
    a.download = filename;
    a.target = "_blank";
    a.click();
  };

  const ExportButton = ({ label, icon: Icon, onClick, color = "primary" }: { label: string; icon: any; onClick: () => void; color?: string }) => (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 bg-${color}-50 text-${color}-700 rounded-lg text-sm font-medium hover:bg-${color}-100 transition-colors border border-${color}-200`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );

  return (
    <div className="container-page">
      <div className="flex items-center gap-3 mb-6">
        <Download className="w-6 h-6 text-primary-600" />
        <div>
          <h1 className="page-title">Export Center</h1>
          <p className="page-subtitle">Download predictions, rankings, and simulation data in JSON or CSV format.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileJson className="w-4 h-4" /> JSON Exports
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Team Profile</span>
              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="px-2 py-1 border border-gray-200 rounded text-xs"
              >
                {teams.map((t: any) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <button
                onClick={() => downloadUrl(`/export/team/${selectedTeam}`, `team-${selectedTeam}.json`)}
                className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs font-medium hover:bg-blue-100 transition-colors"
              >
                Download JSON
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Group Standings</span>
              <select
                value={selectedGroup}
                onChange={(e) => setSelectedGroup(e.target.value)}
                className="px-2 py-1 border border-gray-200 rounded text-xs"
              >
                {groups.map((g: any) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
              <button
                onClick={() => downloadUrl(`/export/group/${selectedGroup}`, `group-${selectedGroup}.json`)}
                className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs font-medium hover:bg-blue-100 transition-colors"
              >
                Download JSON
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Simulation Results</span>
              <select
                value={selectedSim}
                onChange={(e) => setSelectedSim(e.target.value)}
                className="px-2 py-1 border border-gray-200 rounded text-xs"
              >
                {simulations.map((s: Simulation) => (
                  <option key={s.id} value={s.id}>{s.name || s.id.slice(0, 8)}</option>
                ))}
              </select>
              <button
                onClick={() => downloadUrl(`/export/simulation/${selectedSim}`, `simulation-${selectedSim}.json`)}
                className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs font-medium hover:bg-blue-100 transition-colors"
              >
                Download JSON
              </button>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-gray-100">
              <span className="text-sm text-gray-600">All Rankings (Elo / FIFA / IGF)</span>
              <button
                onClick={() => downloadUrl("/export/rankings", "rankings.json")}
                className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs font-medium hover:bg-blue-100 transition-colors"
              >
                Download JSON
              </button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileSpreadsheet className="w-4 h-4" /> CSV Exports
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">
                <Table className="w-4 h-4 inline mr-1" />
                All Matches
              </span>
              <button
                onClick={() => downloadUrl("/export/matches/csv", "matches.csv")}
                className="px-3 py-1.5 bg-green-50 text-green-700 rounded text-xs font-medium hover:bg-green-100 transition-colors"
              >
                Download CSV
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">
                <Table className="w-4 h-4 inline mr-1" />
                Simulation Results
              </span>
              <button
                onClick={() => downloadUrl("/export/simulations/csv", "simulations.csv")}
                className="px-3 py-1.5 bg-green-50 text-green-700 rounded text-xs font-medium hover:bg-green-100 transition-colors"
              >
                Download CSV
              </button>
            </div>

            <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500">
              <FileText className="w-4 h-4 inline mr-1" />
              CSV files can be opened in Excel, Google Sheets, or any spreadsheet application.
              JSON files contain structured data suitable for programmatic use.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
