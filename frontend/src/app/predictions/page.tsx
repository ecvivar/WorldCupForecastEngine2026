"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import { api, type MatchPrediction, type FullMatchPrediction } from "@/lib/api";
import { formatProbability, getStageLabel, getConfidenceColor, formatDate } from "@/lib/utils";
import ProbabilityBar from "@/components/ProbabilityBar";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<MatchPrediction[]>([]);
  const [fullPredictions, setFullPredictions] = useState<Record<string, FullMatchPrediction>>({});
  const [matchStages, setMatchStages] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.predictions.list(),
      api.matches.list(1, 100),
    ])
      .then(async ([list, matches]) => {
        setPredictions(list);
        const stages: Record<string, string> = {};
        for (const m of matches) {
          stages[m.id] = m.stage;
        }
        setMatchStages(stages);
        const fulls: Record<string, FullMatchPrediction> = {};
        await Promise.all(
          list.slice(0, 20).map(async (p) => {
            try {
              const fp = await api.predictions.full(p.match_id);
              fulls[p.match_id] = fp;
            } catch {
              // fallback
            }
          })
        );
        setFullPredictions(fulls);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonPage />;

  if (predictions.length === 0) {
    return (
      <div className="container-page text-center py-12">
        <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold mb-2">No Predictions Yet</h2>
        <p className="text-gray-500">
          Match predictions will appear once matches and IGF data are loaded.
        </p>
      </div>
    );
  }

  return (
    <div className="container-page space-y-6">
      <h1 className="page-title">Match Predictions</h1>
      <p className="page-subtitle">
        {predictions.length} predictions available — click any card for full details
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {predictions.map((p) => {
          const fp = fullPredictions[p.match_id];
          return (
            <Link key={p.match_id} href={`/predictions/${p.match_id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <Badge variant="info" className="text-[10px]">
                      {getStageLabel(matchStages[p.match_id] || "?")}
                    </Badge>
                    {fp && (
                      <Badge className={getConfidenceColor(fp.confidence_index)}>
                        {fp.confidence_level}
                      </Badge>
                    )}
                  </div>

                  <div className="text-center mb-3">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm flex-1 text-right pr-2">
                        {p.home_team}
                      </span>
                      <span className="text-lg font-bold text-primary-600">
                        {p.most_likely_score || "?-?"}
                      </span>
                      <span className="font-bold text-sm flex-1 text-left pl-2">
                        {p.away_team}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      xG: {p.home_expected_goals?.toFixed(2)} — {p.away_expected_goals?.toFixed(2)}
                    </div>
                  </div>

                  <ProbabilityBar
                    homeWin={p.home_win_prob}
                    draw={p.draw_prob}
                    awayWin={p.away_win_prob}
                    height={20}
                  />

                  {fp && (
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                      <span>CI: {fp.confidence_index?.toFixed(0)}</span>
                      <span>|</span>
                      <span>Risk: {(fp.surprise_risk * 100).toFixed(0)}%</span>
                      {fp.btts_prob > 0.5 && (
                        <>
                          <span>|</span>
                          <span>BTTS: {(fp.btts_prob * 100).toFixed(0)}%</span>
                        </>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
