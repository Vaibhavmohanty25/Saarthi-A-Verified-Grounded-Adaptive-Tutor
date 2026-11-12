"use client";

import React, { useState } from "react";
import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";
import { CitationDrawer } from "@/components/CitationDrawer";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FileText,
  Video,
  GitBranch,
  Brain,
  Calculator,
  ShieldAlert,
  Play,
  Layers,
  ChevronRight,
  BarChart3,
  ExternalLink,
} from "lucide-react";
import { MOCK_CONCEPTS, type ChatMessage } from "@/lib/mockData";

export default function LandingPage() {
  const [activeCitation, setActiveCitation] = useState<any | null>(null);
  const [selectedTopic, setSelectedTopic] = useState("Foundational Concepts");
  const [interactiveMessages, setInteractiveMessages] = useState<ChatMessage[]>([
    {
      id: "preview_msg_01",
      sender: "student",
      text: "How does the course outline foundational prerequisite dependencies?",
      timestamp: "10:14 AM",
    },
    {
      id: "preview_msg_02",
      sender: "tutor",
      text: "According to Course Syllabus §2.1 and Lecture 1: Core concepts require mastery of upstream prerequisites before unlocking advanced topics.\n\nEvery explanation provided by Saarthi is strictly indexed to evidence units with verbatim citation anchors.",
      timestamp: "10:14 AM",
      citations: [
        {
          unit_id: "cu_preview_01",
          source: "Course_Syllabus.pdf",
          label: "Section 2.1",
          location: { page: 4 },
          excerpt: "Prerequisites must be mastered before progressing to specialized modules.",
        },
        {
          unit_id: "cu_preview_02",
          source: "Lecture_Session_01.mp4",
          label: "Lec 1 @ 08:30",
          location: { timestamp: "08:30" },
          excerpt: "Foundational definitions establish the structural basis for all follow-up proofs.",
        },
      ],
    },
  ]);

  return (
    <div className="min-h-screen flex flex-col bg-[#fafafa] dark:bg-[#07090e] text-zinc-900 dark:text-zinc-100 transition-colors">
      {/* Top Header */}
      <SiteHeader />

      {/* Hero Section */}
      <section className="relative pt-16 pb-12 sm:pt-24 sm:pb-16 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto text-center">
        
        {/* Giant Main Title */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-zinc-950 dark:text-white max-w-4xl mx-auto leading-[1.1] mb-6 font-sans">
          The AI Tutor That Teaches From Your Course Material.
        </h1>

        {/* Subtitle */}
        <div className="max-w-3xl mx-auto leading-relaxed mb-8 space-y-2.5">
          <p className="text-lg sm:text-xl font-medium text-zinc-850 dark:text-zinc-200">
            Learns from your course. Adapts to you. Verifies every answer.
          </p>
          <p className="text-sm sm:text-base text-zinc-600 dark:text-zinc-400">
            Grounded in your lectures, textbooks, and videos, Saarthi understands what you’re learning, identifies what you’re struggling with, and adapts every question around your mastery — while keeping answers verified and strictly within your course.
          </p>
        </div>

        {/* Call to Actions (Reference image: Try For Free) */}
        <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 mb-16">
          <Link
            href="/chat"
            className="px-7 py-3 rounded-full text-sm font-semibold bg-black dark:bg-white text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all shadow-md hover:shadow-lg flex items-center gap-2 group"
          >
            <span>Try Tutor For Free</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>

          <Link
            href="/graph"
            className="px-6 py-3 rounded-full text-sm font-semibold bg-white dark:bg-white/[0.05] text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-white/[0.1] hover:bg-zinc-50 dark:hover:bg-white/[0.08] transition-all"
          >
            <span>Explore Concept DAG</span>
          </Link>
        </div>

        {/* FRAMED INTERACTIVE PRODUCT PREVIEW (Exact structure of the reference image's card) */}
        <div className="relative mx-auto max-w-5xl rounded-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.1] shadow-2xl overflow-hidden text-left">
          
          {/* Framed Card Top bar / Browser Header */}
          <div className="px-4 py-3 border-b border-zinc-200/80 dark:border-white/[0.08] bg-zinc-50/80 dark:bg-white/[0.02] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
              </div>
              <span className="text-xs font-mono text-zinc-500 ml-2">
                saarthi.ai/course-workspace
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                Live Grounded Session
              </span>
            </div>
          </div>

          {/* 3-Column Framed Interface (Like reference mail UI) */}
          <div className="grid grid-cols-1 md:grid-cols-12 min-h-[460px]">
            
            {/* Left Column: Course Materials & Topics (3 cols) */}
            <div className="md:col-span-3 border-r border-zinc-200 dark:border-white/[0.08] p-4 bg-zinc-50/50 dark:bg-white/[0.01]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Course Materials
                </span>
                <span className="text-[10px] font-mono bg-zinc-200/80 dark:bg-white/[0.08] px-1.5 py-0.5 rounded">
                  Indexed
                </span>
              </div>

              <div className="space-y-1.5 mb-5 text-xs">
                <div className="p-2 rounded-lg bg-white dark:bg-white/[0.06] border border-zinc-200/80 dark:border-white/[0.08] shadow-sm flex items-center gap-2 font-medium">
                  <FileText className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                  <span className="truncate">Course_Syllabus.pdf</span>
                </div>
                <div className="p-2 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-white/[0.04] flex items-center gap-2 transition-colors">
                  <Video className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  <span className="truncate">Lecture_Session_01.mp4</span>
                </div>
                <div className="p-2 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-white/[0.04] flex items-center gap-2 transition-colors">
                  <FileText className="w-3.5 h-3.5 text-purple-500 shrink-0" />
                  <span className="truncate">Course_Readings.pdf</span>
                </div>
              </div>

              <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 block mb-2">
                Knowledge Nodes
              </span>
              <div className="space-y-1 text-xs font-mono">
                {MOCK_CONCEPTS.map((c) => (
                  <button
                    key={c.concept_id}
                    onClick={() => setSelectedTopic(c.name)}
                    className={`w-full text-left px-2.5 py-1.5 rounded-md flex items-center justify-between transition-colors ${
                      selectedTopic === c.name
                        ? "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-semibold"
                        : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-white/[0.03]"
                    }`}
                  >
                    <span className="truncate">{c.name}</span>
                    <span className={`text-[10px] ${c.mastery < 0.5 ? "text-amber-500" : "text-emerald-500"}`}>
                      {Math.round(c.mastery * 100)}%
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Middle Column: Grounded Conversation Preview (6 cols) */}
            <div className="md:col-span-6 p-4 flex flex-col justify-between border-r border-zinc-200 dark:border-white/[0.08]">
              <div>
                <div className="flex items-center justify-between pb-2 mb-3 border-b border-zinc-200/60 dark:border-white/[0.06]">
                  <span className="text-xs font-semibold text-zinc-900 dark:text-white flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    Verified Evidence Stream
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400">
                    Confidence: 98.4%
                  </span>
                </div>

                {/* Messages preview */}
                <div className="space-y-3">
                  {interactiveMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-3 rounded-xl text-xs leading-relaxed ${
                        msg.sender === "student"
                          ? "bg-zinc-100 dark:bg-white/[0.06] text-zinc-900 dark:text-white font-medium ml-4"
                          : "bg-indigo-50/70 dark:bg-indigo-950/20 border border-indigo-200/60 dark:border-indigo-500/20 text-zinc-800 dark:text-zinc-200 mr-4"
                      }`}
                    >
                      <div className="text-[10px] font-mono text-zinc-400 mb-1">
                        {msg.sender === "student" ? "Student Query" : "Saarthi Evidence Grounding"}
                      </div>
                      <p className="whitespace-pre-line">{msg.text}</p>

                      {/* Citation chips */}
                      {msg.citations && (
                        <div className="mt-2.5 pt-2 border-t border-indigo-200/60 dark:border-indigo-500/20 flex flex-wrap gap-1.5">
                          {msg.citations.map((c, i) => (
                            <button
                              key={i}
                              onClick={() => setActiveCitation(c)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono bg-white dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-500/40 hover:bg-indigo-50 dark:hover:bg-indigo-800/60 transition-all cursor-pointer shadow-sm"
                            >
                              <FileText className="w-3 h-3" />
                              <span>[{c.label}]</span>
                              <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Quick direct route CTA */}
              <div className="pt-3 border-t border-zinc-200/60 dark:border-white/[0.06] mt-4 flex items-center justify-between text-xs">
                <span className="text-zinc-500 font-mono text-[11px]">
                  Click chips to inspect verbatim slide citations
                </span>
                <Link
                  href="/chat"
                  className="font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
                >
                  <span>Open Full Chatroom</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>

            {/* Right Column: Assessment & BKT Engine Status (3 cols) */}
            <div className="md:col-span-3 p-4 bg-zinc-50/50 dark:bg-white/[0.01] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                    Learner State (BKT)
                  </span>
                  <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                    74% Total
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-white dark:bg-white/[0.04] border border-zinc-200/80 dark:border-white/[0.06] mb-3 text-xs">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-semibold mb-1">
                    <Brain className="w-3.5 h-3.5" />
                    <span>Prerequisite Gap Found</span>
                  </div>
                  <p className="text-[11px] text-zinc-600 dark:text-zinc-400 leading-snug">
                    Chain Rule mastery (45%) is blocking Neural Networks. Recommended next step: Remediate prerequisite.
                  </p>
                </div>

                {/* Verified question preview */}
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs">
                  <div className="flex items-center gap-1 text-[10px] font-mono text-emerald-700 dark:text-emerald-300 font-semibold mb-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                    <span>Dual-LLM Verified</span>
                  </div>
                  <p className="text-[11px] text-zinc-700 dark:text-zinc-300 font-medium">
                    "y = 3u^2, u = 2x+1. Find dy/dx at x=1"
                  </p>
                  <div className="mt-1.5 flex items-center gap-1 text-[10px] font-mono text-emerald-600 dark:text-emerald-400">
                    <Calculator className="w-3 h-3" />
                    <span>Formally verified: 36</span>
                  </div>
                </div>
              </div>

              <Link
                href="/quiz"
                className="w-full mt-4 py-2 px-3 rounded-xl bg-black dark:bg-white text-white dark:text-black text-center text-xs font-semibold hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all flex items-center justify-center gap-1"
              >
                <span>Launch Quiz Arena</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

          </div>
        </div>

      </section>

      {/* 4 Dedicated Workspace Bento Features */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-zinc-950 dark:text-white">
            Built Across 4 Dedicated Workspaces
          </h2>
          <p className="text-sm sm:text-base text-zinc-600 dark:text-zinc-400 mt-2">
            Each component provides a dedicated view so you can explore every layer.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          
          {/* Card 1: Grounded Chat */}
          <Link
            href="/chat"
            className="group p-5 rounded-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.08] hover:border-indigo-500/50 hover:shadow-xl transition-all"
          >
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-zinc-950 dark:text-white mb-1.5 flex items-center justify-between">
              <span>Grounded Chat</span>
              <ArrowRight className="w-4 h-4 text-zinc-400 group-hover:text-indigo-500 transition-colors" />
            </h3>
            <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
              Every answer backed by page, slide number, or video timestamp. Includes transparent refusal for out-of-scope topics.
            </p>
          </Link>

          {/* Card 2: Concept Graph */}
          <Link
            href="/graph"
            className="group p-5 rounded-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.08] hover:border-indigo-500/50 hover:shadow-xl transition-all"
          >
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <GitBranch className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-zinc-950 dark:text-white mb-1.5 flex items-center justify-between">
              <span>Concept Graph DAG</span>
              <ArrowRight className="w-4 h-4 text-zinc-400 group-hover:text-purple-500 transition-colors" />
            </h3>
            <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
              Curriculum prerequisite hierarchy linking concepts to exact evidence units with backward-walk remediation.
            </p>
          </Link>

          {/* Card 3: Adaptive Quiz */}
          <Link
            href="/quiz"
            className="group p-5 rounded-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.08] hover:border-emerald-500/50 hover:shadow-xl transition-all"
          >
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Brain className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-zinc-950 dark:text-white mb-1.5 flex items-center justify-between">
              <span>Adaptive Quiz Arena</span>
              <ArrowRight className="w-4 h-4 text-zinc-400 group-hover:text-emerald-500 transition-colors" />
            </h3>
            <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
              Dual model generation with automated mathematical checking. Real-time adaptive mastery tracing per topic.
            </p>
          </Link>

          {/* Card 4: Ablation Bench */}
          <Link
            href="/benchmark"
            className="group p-5 rounded-2xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.08] hover:border-blue-500/50 hover:shadow-xl transition-all"
          >
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <BarChart3 className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-zinc-950 dark:text-white mb-1.5 flex items-center justify-between">
              <span>Ablation Benchmark</span>
              <ArrowRight className="w-4 h-4 text-zinc-400 group-hover:text-blue-500 transition-colors" />
            </h3>
            <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
              Simulated student trajectories: Adaptive (+74%) vs Random (47%) plus automated RAGAS faithfulness metrics.
            </p>
          </Link>

        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 border-t border-zinc-200 dark:border-white/[0.08] text-center text-xs text-zinc-500 font-mono">
        <p>Saarthi · Verified-Grounded Adaptive Tutor</p>
      </footer>

      {/* Citation Drawer Modal */}
      <CitationDrawer
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
