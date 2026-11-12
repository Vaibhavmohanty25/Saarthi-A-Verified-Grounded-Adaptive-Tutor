"use client";

import React from "react";
import { X, TrendingUp, BarChart3, CheckCircle, ShieldAlert, Award, Sparkles } from "lucide-react";
import { formatMetric } from "@/lib/api";
import { EVALUATION_ABLATION_DATA } from "@/lib/mockData";

interface EvaluationAblationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EvaluationAblationModal({
  isOpen,
  onClose,
}: EvaluationAblationModalProps) {
  if (!isOpen) return null;

  const { ragas_metrics, learning_curves, ablation_summary } = EVALUATION_ABLATION_DATA;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 dark:bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.12] rounded-2xl shadow-2xl p-6 overflow-hidden max-h-[90vh] flex flex-col">
        
        {/* Glow ambient background */}
        <div className="absolute top-0 left-1/3 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-zinc-200 dark:border-white/[0.08] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/10 dark:bg-purple-500/15 border border-purple-500/20 dark:border-purple-500/25 text-purple-600 dark:text-purple-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-zinc-900 dark:text-white">
                  System Evaluation & Benchmark Bench
                </h3>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20 dark:border-indigo-500/25">
                  Empirical Benchmark
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Simulated Learner Experiment: Adaptive BKT vs. Random Baseline & RAGAS Harness
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto py-4 space-y-5 flex-1 pr-1">
          
          {/* Key Metric Headline */}
          <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-50 dark:from-indigo-950/40 to-purple-50 dark:to-purple-950/20 border border-indigo-200 dark:border-indigo-500/30 flex items-center justify-between">
            <div>
              <span className="text-xs font-bold uppercase text-indigo-700 dark:text-indigo-300 tracking-wider">
                Personalization Gain (5 Sessions)
              </span>
              <div className="text-2xl font-extrabold text-indigo-950 dark:text-white mt-0.5">
                {ablation_summary.net_mastery_gain} Mastery Acceleration
              </div>
              <p className="text-xs text-zinc-600 dark:text-zinc-300 mt-1">
                {ablation_summary.sample_size} (p {ablation_summary.p_value})
              </p>
            </div>
            <div className="p-3 rounded-2xl bg-indigo-500/15 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-300 border border-indigo-400/30">
              <TrendingUp className="w-8 h-8" />
            </div>
          </div>

          {/* Comparison Table / Bar Visualization */}
          <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
            <h4 className="text-xs font-bold text-zinc-900 dark:text-white mb-3 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              Learning Trajectory: Adaptive BKT vs. Random Selection
            </h4>

            <div className="space-y-3">
              {learning_curves.map((curve, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    <span>{curve.session}</span>
                    <div className="flex gap-4">
                      <span className="text-zinc-500">Random: {curve.random}%</span>
                      <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                        Adaptive: {curve.adaptive}%
                      </span>
                    </div>
                  </div>

                  {/* Dual progress bar */}
                  <div className="w-full bg-zinc-200 dark:bg-white/[0.04] h-3 rounded-full flex overflow-hidden p-0.5 gap-1">
                    <div
                      className="h-full bg-zinc-400 dark:bg-zinc-600 rounded-full transition-all"
                      style={{ width: `${curve.random}%` }}
                    />
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 dark:to-emerald-400 rounded-full transition-all"
                      style={{ width: `${curve.adaptive - curve.random}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end gap-4 mt-3 text-xs font-semibold">
              <span className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-400 dark:bg-zinc-600 inline-block" />
                Random Question Baseline
              </span>
              <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 dark:bg-emerald-400 inline-block" />
                Saarthi Adaptive Prerequisite
              </span>
            </div>
          </div>

          {/* RAGAS Framework Scores */}
          <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
            <h4 className="text-xs font-bold text-zinc-900 dark:text-white mb-3">
              RAGAS Retrieval & Generation Evaluation Matrix
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <div className="p-3 rounded-lg bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
                <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase block">Faithfulness</span>
                <span className="text-base font-extrabold text-zinc-900 dark:text-white">
                  {formatMetric(ragas_metrics.faithfulness)}
                </span>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 block mt-0.5 font-medium">Grounding pass</span>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
                <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase block">Answer Relevancy</span>
                <span className="text-base font-extrabold text-zinc-900 dark:text-white">
                  {formatMetric(ragas_metrics.answer_relevancy)}
                </span>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 block mt-0.5 font-medium">High precision</span>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
                <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase block">Context Precision</span>
                <span className="text-base font-extrabold text-zinc-900 dark:text-white">
                  {formatMetric(ragas_metrics.context_precision)}
                </span>
                <span className="text-xs text-indigo-600 dark:text-indigo-400 block mt-0.5 font-medium">Top-3 reranked</span>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06]">
                <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase block">Context Recall</span>
                <span className="text-base font-extrabold text-zinc-900 dark:text-white">
                  {formatMetric(ragas_metrics.context_recall)}
                </span>
                <span className="text-xs text-indigo-600 dark:text-indigo-400 block mt-0.5 font-medium">Full coverage</span>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] col-span-2 sm:col-span-1">
                <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase block">Refusal Precision</span>
                <span className="text-base font-extrabold text-emerald-600 dark:text-emerald-400">
                  {formatMetric(ragas_metrics.refusal_precision)}
                </span>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 block mt-0.5 font-medium">Zero hallucination</span>
              </div>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="pt-3.5 border-t border-zinc-200 dark:border-white/[0.08] flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 shrink-0">
          <span className="text-xs font-medium">
            Evaluated on Adaptive Mastery Benchmark Testset (N=50)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-black dark:bg-white/[0.08] hover:bg-zinc-800 dark:hover:bg-white/[0.12] text-xs text-white font-semibold transition-all cursor-pointer"
          >
            Done
          </button>
        </div>

      </div>
    </div>
  );
}
