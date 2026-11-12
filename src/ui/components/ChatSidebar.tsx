"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  SquarePen,
  Trash2,
  CheckCircle2,
  Languages,
  BookOpen,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Trophy,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  GraduationCap,
  BarChart3,
  Home,
  X,
} from "lucide-react";
import {
  ChatSession,
  CompletedQuiz,
  listSessions,
  createSession,
  deleteSession,
  fetchCompletedQuizzes,
} from "@/lib/api";

/* ───────────────────────────── Types ───────────────────────────── */
interface ChatSidebarProps {
  currentSessionId?: string;
  onSessionSelect: (session: ChatSession) => void;
  onNewChat: (session: ChatSession) => void;
  studentId?: string;
  hindiMode: boolean;
  onHindiModeToggle: () => void;
  showEvidenceInspector: boolean;
  onEvidenceToggle: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  refreshTrigger?: number;
}

/* ─────────────────── Date-group helpers ───────────────────────── */
function getDateLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 86400000;
  if (diff < 1) return "Today";
  if (diff < 2) return "Yesterday";
  if (diff < 7) return "Last 7 days";
  if (diff < 30) return "Last 30 days";
  return d.toLocaleString("default", { month: "long", year: "numeric" });
}

function groupSessions(sessions: ChatSession[]) {
  const order = ["Today", "Yesterday", "Last 7 days", "Last 30 days"];
  const map: Record<string, ChatSession[]> = {};
  for (const s of sessions) {
    const label = getDateLabel(s.updated_at);
    if (!map[label]) map[label] = [];
    map[label].push(s);
  }
  const sorted: { label: string; sessions: ChatSession[] }[] = [];
  for (const key of order) {
    if (map[key]) sorted.push({ label: key, sessions: map[key] });
  }
  for (const [key, val] of Object.entries(map)) {
    if (!order.includes(key)) sorted.push({ label: key, sessions: val });
  }
  return sorted;
}

function quizGrade(score: number, total: number) {
  const pct = total > 0 ? Math.round((score / total) * 100) : 0;
  if (pct >= 80) return { color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" };
  if (pct >= 60) return { color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" };
  return { color: "text-rose-600 dark:text-rose-400", bg: "bg-rose-500/10 border-rose-500/20" };
}

/* ═══════════════════════════ Component ═══════════════════════════ */
export function ChatSidebar({
  currentSessionId,
  onSessionSelect,
  onNewChat,
  studentId = "student_default",
  hindiMode,
  onHindiModeToggle,
  showEvidenceInspector,
  onEvidenceToggle,
  isCollapsed,
  onToggleCollapse,
  refreshTrigger = 0,
}: ChatSidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [completedQuizzes, setCompletedQuizzes] = useState<CompletedQuiz[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [creatingNew, setCreatingNew] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(true);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  /* ─── Data loading ─── */
  const loadData = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const [s, q] = await Promise.all([
        listSessions(studentId),
        fetchCompletedQuizzes(studentId),
      ]);
      setSessions(s);
      setCompletedQuizzes(q);
    } catch (error) {
      console.warn("Could not load the chat sidebar:", error);
    } finally {
      setLoadingSessions(false);
    }
  }, [studentId]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshTrigger]);

  /* ─── New chat ─── */
  const handleNewChat = async () => {
    setCreatingNew(true);
    try {
      const s = await createSession(studentId);
      setSessions((prev) => [s, ...prev]);
      onNewChat(s);
    } catch {
      const placeholder: ChatSession = {
        id: `local_${Date.now()}`,
        student_id: studentId,
        title: "New Chat",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0,
      };
      onNewChat(placeholder);
    } finally {
      setCreatingNew(false);
    }
  };

  /* ─── Delete session ─── */
  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeletingId(id);
    try {
      await deleteSession(id, studentId);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (error) {
      console.warn("Could not delete the chat session:", error);
    } finally {
      setDeletingId(null);
    }
  };

  const groups = groupSessions(sessions);

  return (
    <aside
      className={`relative flex flex-col bg-white dark:bg-[#0c101c] border-r border-zinc-200/90 dark:border-white/[0.08] transition-all duration-200 shrink-0 h-full overflow-hidden ${
        isCollapsed
          ? "w-0 md:w-[60px]"
          : "w-[260px] sm:w-[280px]"
      }`}
      aria-label="Chat sidebar"
    >

        {/* If collapsed on desktop: Icon-only minimal bar */}
        {isCollapsed ? (
          <div className="hidden md:flex flex-col items-center py-3 gap-2.5 h-full w-full">
            <button
              onClick={onToggleCollapse}
              className="p-2 rounded-xl text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.06] transition-all cursor-pointer"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>

            <button
              onClick={handleNewChat}
              className="p-2 rounded-xl text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-all cursor-pointer"
              title="New chat"
            >
              <SquarePen className="w-4 h-4" />
            </button>

            <div className="flex-1" />

            <button
              onClick={onHindiModeToggle}
              className={`p-2 rounded-xl transition-all cursor-pointer ${
                hindiMode
                  ? "text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/15"
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
              title="Hindi Mode"
            >
              <Languages className="w-4 h-4" />
            </button>

            <button
              onClick={onEvidenceToggle}
              className={`p-2 rounded-xl transition-all cursor-pointer ${
                showEvidenceInspector
                  ? "text-indigo-600 bg-indigo-50 dark:text-indigo-400 dark:bg-indigo-500/15"
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
              title="Evidence Inspector"
            >
              <BookOpen className="w-4 h-4" />
            </button>

            <Link
              href="/"
              className="p-2 rounded-xl text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-all mb-2"
              title="Home"
            >
              <Home className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          /* Expanded Full-feature Sidebar View */
          <div className="flex flex-col h-full w-full">
            {/* Header: Brand & Close button */}
            <div className="flex items-center justify-between px-3.5 pt-3.5 pb-2 shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 shadow-md shadow-indigo-500/20 text-white font-bold">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
                <span className="text-sm font-bold text-zinc-900 dark:text-white tracking-tight">
                  Saarthi Chat
                </span>
              </div>
              <button
                onClick={onToggleCollapse}
                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.06] transition-all cursor-pointer"
                title="Collapse sidebar"
              >
                <PanelLeftClose className="w-4 h-4 hidden md:block" />
                <X className="w-4 h-4 md:hidden" />
              </button>
            </div>

            {/* New Chat Button */}
            <div className="px-3 pt-1 pb-2 shrink-0">
              <button
                id="new-chat-btn"
                onClick={handleNewChat}
                disabled={creatingNew}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl bg-zinc-100 hover:bg-indigo-50 dark:bg-white/[0.04] dark:hover:bg-indigo-500/10 border border-zinc-200/80 hover:border-indigo-300 dark:border-white/[0.07] dark:hover:border-indigo-500/25 text-xs sm:text-sm text-zinc-800 dark:text-zinc-200 hover:text-indigo-600 dark:hover:text-white font-semibold transition-all cursor-pointer group disabled:opacity-50 shadow-2xs"
              >
                <SquarePen className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span>{creatingNew ? "Creating..." : "New Chat"}</span>
              </button>
            </div>

            {/* Scrollable Sessions & Completed Quizzes */}
            <div className="flex-1 overflow-y-auto px-2.5 pb-2 space-y-4">
              {loadingSessions ? (
                <div className="space-y-1.5 px-1 mt-1">
                  {[...Array(4)].map((_, i) => (
                    <div
                      key={i}
                      className="h-8 rounded-lg bg-zinc-200/60 dark:bg-white/[0.03] animate-pulse"
                      style={{ animationDelay: `${i * 80}ms` }}
                    />
                  ))}
                </div>
              ) : sessions.length === 0 ? (
                <div className="px-3 py-8 text-center">
                  <MessageSquare className="w-7 h-7 mx-auto text-zinc-400 dark:text-zinc-600 mb-2" />
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                    No chat history yet. Click <strong className="text-zinc-800 dark:text-zinc-200">New Chat</strong> to begin.
                  </p>
                </div>
              ) : (
                groups.map((group) => (
                  <div key={group.label}>
                    <p className="px-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                      {group.label}
                    </p>
                    <div className="space-y-0.5">
                      {group.sessions.map((session) => {
                        const isActive = session.id === currentSessionId;
                        const isDeleting = deletingId === session.id;
                        return (
                          <div
                            key={session.id}
                            onMouseEnter={() => setHoveredId(session.id)}
                            onMouseLeave={() => setHoveredId(null)}
                            onClick={() => onSessionSelect(session)}
                            className={`relative flex items-center gap-2 px-2.5 py-2 rounded-xl cursor-pointer group transition-all text-xs leading-relaxed ${
                              isActive
                                ? "bg-indigo-50 dark:bg-indigo-600/20 text-indigo-950 dark:text-white font-semibold border border-indigo-200/70 dark:border-indigo-500/30"
                                : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-white/[0.04] hover:text-zinc-950 dark:hover:text-zinc-200"
                            } ${isDeleting ? "opacity-40 pointer-events-none" : ""}`}
                          >
                            <MessageSquare
                              className={`w-3.5 h-3.5 shrink-0 ${
                                isActive ? "text-indigo-600 dark:text-indigo-400" : "text-zinc-400 dark:text-zinc-500"
                              }`}
                            />
                            <span className="flex-1 truncate">{session.title}</span>

                            {(hoveredId === session.id || isActive) && (
                              <button
                                onClick={(e) => handleDelete(e, session.id)}
                                className="shrink-0 p-1 rounded-md text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-all cursor-pointer"
                                title="Delete chat"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}

              {/* Completed Quizzes / Assessments Section */}
              {completedQuizzes.length > 0 && (
                <div className="pt-2 border-t border-zinc-100 dark:border-white/[0.04]">
                  <button
                    onClick={() => setShowCompleted((v) => !v)}
                    className="w-full flex items-center gap-1.5 px-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors cursor-pointer"
                  >
                    <Trophy className="w-3 h-3" />
                    <span>Completed Quizzes ({completedQuizzes.length})</span>
                    {showCompleted ? (
                      <ChevronDown className="w-3 h-3 ml-auto" />
                    ) : (
                      <ChevronRight className="w-3 h-3 ml-auto" />
                    )}
                  </button>

                  {showCompleted && (
                    <div className="space-y-1 mt-1">
                      {completedQuizzes.slice(0, 8).map((q) => {
                        const { color, bg } = quizGrade(q.score, q.total);
                        return (
                          <div
                            key={q.id}
                            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-zinc-600 dark:text-zinc-400 bg-zinc-50/70 dark:bg-white/[0.02]"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                            <span className="flex-1 truncate">{q.topic || "Quiz"}</span>
                            <span
                              className={`shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${bg} ${color}`}
                            >
                              {q.score}/{q.total}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer Controls */}
            <div className="shrink-0 border-t border-zinc-200/80 dark:border-white/[0.06] p-2.5 space-y-1 bg-zinc-50/50 dark:bg-transparent">
              <button
                onClick={onHindiModeToggle}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  hindiMode
                    ? "bg-amber-100/80 text-amber-900 border border-amber-300/80 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/25"
                    : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/[0.04]"
                }`}
              >
                <Languages className="w-3.5 h-3.5 shrink-0" />
                <span>{hindiMode ? "🇮🇳 Hindi Mode (Active)" : "Hindi Mode"}</span>
              </button>

              <button
                onClick={onEvidenceToggle}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  showEvidenceInspector
                    ? "bg-indigo-100/80 text-indigo-900 border border-indigo-300/80 dark:bg-indigo-500/15 dark:text-indigo-300 dark:border-indigo-500/25"
                    : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/[0.04]"
                }`}
              >
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <span>Evidence Inspector</span>
              </button>

              <div className="flex items-center gap-1 pt-1">
                <Link
                  href="/"
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.04] transition-all"
                >
                  <Home className="w-3 h-3" />
                  <span>Home</span>
                </Link>
                <Link
                  href="/quiz"
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.04] transition-all"
                >
                  <GraduationCap className="w-3 h-3" />
                  <span>Quiz</span>
                </Link>
                <Link
                  href="/graph"
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.04] transition-all"
                >
                  <BarChart3 className="w-3 h-3" />
                  <span>Graph</span>
                </Link>
              </div>
            </div>
          </div>
        )}
      </aside>
  );
}

