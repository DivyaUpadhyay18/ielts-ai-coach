'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layouts/dashboard-layout';
import { PredictionWidget } from '@/components/prediction/prediction-widget';
import { predictionService } from '@/services/api';
import type { PredictionResponse, PredictionHistoryItem } from '@/types';

export default function PredictionPage() {
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [history, setHistory] = useState<PredictionHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [predictionData, historyData] = await Promise.all([
        predictionService.getPrediction(),
        predictionService.getHistory(10, 0),
      ]);
      setPrediction(predictionData);
      setHistory(historyData.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load prediction data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Prediction Engine</h1>
          <p className="text-muted-foreground">
            Deterministic exam readiness estimates based on your study data.
          </p>
        </div>

        {error && (
          <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-sm text-muted-foreground">Computing prediction...</div>
          </div>
        ) : prediction ? (
          <div className="space-y-6">
            <PredictionWidget prediction={prediction} onRefresh={fetchData} />

            {history.length > 0 && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h2 className="text-lg font-semibold mb-4">Prediction History</h2>
                <div className="space-y-3">
                  {history.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-md border border-border/60 bg-background p-3"
                    >
                      <div>
                        <div className="text-sm font-medium">
                          {new Date(item.run_date).toLocaleDateString()}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Readiness: {item.readiness_score.toFixed(1)} • Risk: {item.risk_level}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold">
                          {item.estimated_band.toFixed(1)} band
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {item.preparation_percentage.toFixed(1)}% prepared
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-md border border-border bg-card p-6 text-center text-sm text-muted-foreground">
            No prediction available yet. Complete some study activity to generate your first prediction.
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
