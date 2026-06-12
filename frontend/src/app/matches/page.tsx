"use client";

import { useEffect, useState } from "react";
import { api, Match } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage, SkeletonCard } from "@/components/ui/skeleton";
import { formatDate, getStageLabel } from "@/lib/utils";

export default function MatchesPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.matches.list(1, 100).then(setMatches).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonPage />;

  const byStage: Record<string, Match[]> = {};
  matches.forEach((m) => {
    if (!byStage[m.stage]) byStage[m.stage] = [];
    byStage[m.stage].push(m);
  });

  return (
    <div className="container-page">
      <h1 className="page-title">Matches</h1>
      <p className="page-subtitle mb-6">All 104 tournament fixtures.</p>

      {Object.entries(byStage).map(([stage, stageMatches]) => (
        <div key={stage} className="mb-8">
          <h2 className="mb-3 text-lg font-semibold text-gray-700">
            {getStageLabel(stage)}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {stageMatches.map((m) => (
              <Card key={m.id}>
                <CardContent className="p-4">
                  <div className="mb-2 text-xs text-gray-500">
                    {formatDate(m.match_date)}
                    {m.group_name && <> &middot; Group {m.group_name}</>}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{m.home_team_id.slice(0, 8)}...</span>
                    <span className="mx-3 font-bold text-gray-900">
                      {m.home_goals !== null ? `${m.home_goals} - ${m.away_goals}` : "vs"}
                    </span>
                    <span className="font-medium">{m.away_team_id.slice(0, 8)}...</span>
                  </div>
                  <Badge variant={m.status === "finished" ? "success" : "default"} className="mt-2">
                    {m.status}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
