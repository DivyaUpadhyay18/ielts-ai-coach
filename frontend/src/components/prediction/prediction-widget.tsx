'use client';

import { useState } from 'react';
import { RefreshCw, AlertTriangle, TrendingUp, Target, Clock, CheckCircle2, Flame, BarChart3 } from 'lucide-react';
import type { PredictionResponse } from '@/types';

interface PredictionWidgetProps {
  prediction: PredictionResponse;
  onRefresh: () => void;
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  critical: 'bg-red-100 text-red-700 border-red-200',
};

const RISK_LABELS: Record<string, string> = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
  critical: 'Critical Risk',
};

export function PredictionWidget({ prediction, onRefresh }: PredictionWidgetProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setRefreshing(false);
  };

  const { metrics, risk_level, readiness_score, estimated_band, target_band, current_band, recommendations } = prediction;

  return (
    <div className="space-y-4">
      {/* Main score cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Readiness Score */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Readiness Score</span>
            <Target className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{readiness_score.toFixed(1)}</div>
          <div className="text-xs text-muted-foreground">out of 100</div>
        </div>

        {/* Estimated Band */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Estimated Band</span>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{estimated_band.toFixed(1)}</div>
          <div className="text-xs text-muted-foreground">
            target: {target_band?.toFixed(1) ?? '—'}
          </div>
        </div>

        {/* Completion Rate */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Completion Rate</span>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{metrics.completion_rate.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground">
            {metrics.completed_tasks}/{metrics.total_tasks - metrics.skipped_tasks} tasks
          </div>
        </div>

        {/* Risk Level */}
        <div className={`rounded-lg border p-4 ${RISK_COLORS[risk_level] || 'bg-muted'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium opacity-80">Risk Level</span>
            <AlertTriangle className="h-4 w-4 opacity-80" />
          </div>
          <div className="text-2xl font-bold">{RISK_LABELS[risk_level] || risk_level}</div>
          <div className="text-xs opacity-80">
            {metrics.days_remaining} days remaining
          </div>
        </div>
      </div>

      {/* Secondary metrics */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Study Consistency */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Study Consistency</span>
            <Flame className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-xl font-semibold">{metrics.study_consistency.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground">
            {metrics.active_days}/{metrics.total_days_since_start} active days
          </div>
        </div>

        {/* Study Time */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Total Study Time</span>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-xl font-semibold">{metrics.study_hours.toFixed(1)} hrs</div>
          <div className="text-xs text-muted-foreground">
            {metrics.study_minutes} minutes logged
          </div>
        </div>

        {/* Mock Tests */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground">Mock Tests</span>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-xl font-semibold">
            {metrics.mock_test_count > 0 ? `${metrics.average_mock_band?.toFixed(1)} avg` : 'None yet'}
          </div>
          <div className="text-xs text-muted-foreground">
            {metrics.mock_test_count} test{metrics.mock_test_count === 1 ? '' : 's'} taken
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Recommendations</h3>
          <ul className="space-y-2">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <span className="mt-1 h-2 w-2 rounded-full bg-primary" />
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Formulas (collapsible) */}
      <details className="rounded-lg border border-border bg-card">
        <summary className="cursor-pointer p-4 text-sm font-medium text-muted-foreground hover:text-foreground">
          View Formulas & Methodology
        </summary>
        <div className="border-t border-border p-4 space-y-3 text-xs text-muted-foreground">
          {Object.entries(prediction.formulas).map(([key, formula]) => (
            <div key={key}>
              <div className="font-semibold text-foreground mb-1">{key}</div>
              <p>{formula}</p>
            </div>
          ))}
        </div>
      </details>

      {/* Refresh button */}
      <div className="flex justify-end">
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Recompute Prediction
        </button>
      </div>
    </div>
  );
}
