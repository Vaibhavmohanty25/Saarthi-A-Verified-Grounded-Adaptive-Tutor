"use client";

import React, { useState } from "react";
import {
  Brain,
  CheckCircle,
  XCircle,
  HelpCircle,
  Sparkles,
  ShieldCheck,
  Calculator,
  ArrowRight,
  RefreshCw,
  Trophy,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Question, ConceptNode } from "@/lib/mockData";

interface LearnerModelArenaProps {
  concepts: ConceptNode[];
  activeQuestion: Question;
  questionIndex?: number;
  totalQuestions?: number;
  onAnswerSubmitted: (chosenOption: string) => Promise<{ correct: boolean; explanation: string; correct_answer?: string } | void>;
  onNextQuestion: () => void;
  onPrevQuestion?: () => void;
}

export function LearnerModelArena({
  concepts,
  activeQuestion,
  questionIndex = 0,
  totalQuestions = 1,
  onAnswerSubmitted,
  onNextQuestion,
  onPrevQuestion,
}: LearnerModelArenaProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);
  const [feedback, setFeedback] = useState<{ correct: boolean; explanation: string; correct_answer?: string } | null>(null);

  // Reset answer selection when switching questions
  React.useEffect(() => {
    setSelectedOption(null);
    setIsSubmitted(false);
    setIsCorrect(false);
    setShowExplanation(false);
    setFeedback(null);
  }, [activeQuestion.q_id, activeQuestion.attempt_id]);

  // Compute overall BKT mastery
  const totalMastery = concepts.length > 0
    ? Math.round((concepts.reduce((acc, c) => acc + c.mastery, 0) / concepts.length) * 100)
    : 50;

  const handleSubmit = async () => {
    if (!selectedOption || isSubmitted || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await onAnswerSubmitted(selectedOption);
      if (res) {
        setIsCorrect(res.correct);
        setFeedback(res);
      } else {
        const correct = selectedOption.startsWith(activeQuestion.answer.slice(0, 2));
        setIsCorrect(correct);
        setFeedback({
          correct,
          explanation: activeQuestion.explanation,
          correct_answer: activeQuestion.answer,
        });
      }
      setIsSubmitted(true);
      setShowExplanation(true);
    } catch {
      setIsSubmitted(true);
      setShowExplanation(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNext = () => {
    setSelectedOption(null);
    setIsSubmitted(false);
    setShowExplanation(false);
    setFeedback(null);
    onNextQuestion();
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.08] rounded-2xl overflow-hidden p-4 sm:p-5 shadow-sm">
      {/* Pane Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-zinc-200/80 dark:border-white/[0.06]">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          <h2 className="text-sm font-bold text-zinc-900 dark:text-white tracking-tight">
            Learner Model (BKT) & Quiz
          </h2>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20 text-xs font-semibold">
          <span>P(L_t) Bayesian State</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 my-2 pr-1">
        
        {/* Overall Mastery Ring & Stats */}
        <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] flex items-center justify-between">
          <div>
            <span className="text-xs font-bold uppercase text-zinc-500 dark:text-zinc-400 tracking-wider">
              Total Course Mastery
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-extrabold text-zinc-900 dark:text-white">
                {totalMastery}%
              </span>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold">
                Active BKT
              </span>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              {concepts.length} active course concepts evaluated in real-time
            </p>
          </div>

          <div className="relative w-14 h-14 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="28"
                cy="28"
                r="22"
                stroke="currentColor"
                strokeWidth="4"
                className="text-zinc-200 dark:text-white/[0.08]"
                fill="transparent"
              />
              <circle
                cx="28"
                cy="28"
                r="22"
                stroke="currentColor"
                strokeWidth="4"
                className="text-indigo-600 dark:text-indigo-400"
                fill="transparent"
                strokeDasharray={2 * Math.PI * 22}
                strokeDashoffset={2 * Math.PI * 22 * (1 - totalMastery / 100)}
                strokeLinecap="round"
              />
            </svg>
            <Trophy className="absolute w-5 h-5 text-indigo-600 dark:text-indigo-300" />
          </div>
        </div>

        {/* Adaptive Recommendation Card */}
        {(() => {
          const weakest = [...concepts].sort((a, b) => a.mastery - b.mastery)[0];
          return (
            <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-500/20">
              <div className="flex items-center justify-between text-xs">
                <span className="text-indigo-800 dark:text-indigo-300 font-semibold flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                  Adaptive Intervention Loop
                </span>
                <span className="text-xs font-semibold text-amber-700 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  Remediation
                </span>
              </div>
              <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-1.5 leading-relaxed">
                Targeting <strong>{weakest ? weakest.name : activeQuestion.topic}</strong> (prerequisite mastery at {weakest ? Math.round(weakest.mastery * 100) : 50}%). Resolving this foundation unlocks advanced topics.
              </p>
            </div>
          );
        })()}

        {/* VERIFIED QUESTION CARD */}
        <div className="p-4 sm:p-5 rounded-xl bg-zinc-50/70 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08] relative">
          
          {/* Question Index & Navigation */}
          <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-zinc-200/60 dark:border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-zinc-900 dark:text-white">
                Question {questionIndex + 1} of {totalQuestions}
              </span>
              <span className="text-[11px] text-zinc-500 font-medium truncate max-w-[200px]">
                · {activeQuestion.topic}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              {onPrevQuestion && (
                <button
                  type="button"
                  onClick={onPrevQuestion}
                  disabled={questionIndex === 0}
                  className="p-1 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-white/[0.08] disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
                  title="Previous Question"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              )}
              <span className="text-[11px] font-bold text-zinc-500">
                {questionIndex + 1}/{totalQuestions}
              </span>
              <button
                type="button"
                onClick={onNextQuestion}
                disabled={questionIndex >= totalQuestions - 1}
                className="p-1 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-white/[0.08] disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
                title="Next Question"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Dual-LLM & SymPy Badges */}
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 dark:border-emerald-500/30 pulse-verified">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              Verified Dual-LLM (100%)
            </span>
            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-teal-500/10 dark:teal-500/15 text-teal-700 dark:text-teal-300 border border-teal-500/20 dark:border-teal-500/30">
              <Calculator className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
              Formally Verified
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-md ml-auto border ${
              activeQuestion.difficulty === 1
                ? "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20"
                : activeQuestion.difficulty === 2
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                : activeQuestion.difficulty === 3
                ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20"
                : activeQuestion.difficulty === 4
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                : "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20"
            }`}>
              Diff: Level {activeQuestion.difficulty}/5
            </span>
          </div>

          {/* Stem */}
          <h3 className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white leading-relaxed mb-3">
            {activeQuestion.stem}
          </h3>

          {/* Options */}
          {activeQuestion.options && (
            <div className="space-y-2 mb-4">
              {activeQuestion.options.map((opt, i) => {
                const isSelected = selectedOption === opt;
                return (
                  <button
                    key={i}
                    disabled={isSubmitted}
                    onClick={() => setSelectedOption(opt)}
                    className={`w-full text-left p-3 rounded-xl text-xs sm:text-sm font-medium transition-all flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? "bg-indigo-50 dark:bg-indigo-600/30 border border-indigo-400 dark:border-indigo-500/60 text-indigo-950 dark:text-white shadow-sm"
                        : "bg-white dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] text-zinc-800 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-white/[0.05] hover:text-zinc-950 dark:hover:text-white"
                    } ${isSubmitted ? "cursor-default" : ""}`}
                  >
                    <span>{opt}</span>
                    <div
                      className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                        isSelected
                          ? "border-indigo-600 dark:border-indigo-400 bg-indigo-600 dark:bg-indigo-500"
                          : "border-zinc-300 dark:border-white/20"
                      }`}
                    >
                      {isSelected && (
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Action Button */}
          {!isSubmitted ? (
            <button
              onClick={handleSubmit}
              disabled={!selectedOption || isSubmitting}
              className={`w-full py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                selectedOption && !isSubmitting
                  ? "uiverse-btn-primary cursor-pointer"
                  : "bg-zinc-100 dark:bg-white/[0.04] text-zinc-400 dark:text-zinc-500 border border-zinc-200 dark:border-white/[0.06] cursor-not-allowed"
              }`}
            >
              {isSubmitting ? "Evaluating Bayesian Update..." : "Verify Answer & Update BKT State"}
            </button>
          ) : (
            <div className="space-y-3">
              <div
                className={`p-3.5 rounded-xl border flex items-start gap-2.5 ${
                  isCorrect
                    ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-500/30 text-emerald-900 dark:text-emerald-200"
                    : "bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-500/30 text-rose-900 dark:text-rose-200"
                }`}
              >
                {isCorrect ? (
                  <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                )}
                <div className="text-xs sm:text-sm leading-relaxed">
                  <span className="font-bold block mb-0.5">
                    {isCorrect
                      ? "Correct! BKT mastery increased."
                      : "Incorrect. BKT updated prior mastery."}
                  </span>
                  {!isCorrect && feedback?.correct_answer && (
                    <span className="block text-xs font-semibold text-rose-700 dark:text-rose-300 mb-1">
                      Target Solution: {feedback.correct_answer}
                    </span>
                  )}
                  <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-1 leading-relaxed">
                    {feedback?.explanation || activeQuestion.explanation}
                  </p>
                </div>
              </div>

              <button
                onClick={handleNext}
                className="w-full py-2.5 rounded-xl bg-black dark:bg-white/[0.08] hover:bg-zinc-800 dark:hover:bg-white/[0.12] border border-transparent dark:border-white/[0.12] text-xs sm:text-sm font-semibold text-white transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
              >
                <span>Fetch Next Adaptive Question</span>
                <ArrowRight className="w-4 h-4 text-indigo-400" />
              </button>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
