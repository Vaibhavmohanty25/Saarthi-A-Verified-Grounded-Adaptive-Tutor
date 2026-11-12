"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Sparkles,
  Send,
  Loader2,
  Paperclip,
  PanelLeftOpen,
  PanelLeftClose,
  UploadCloud,
  FileText,
  Video,
  ShieldAlert,
  Languages,
  BookOpen,
  ChevronRight,
  GraduationCap,
  CheckCircle2,
  Copy,
  Check,
  X,
  Layers,
  Menu,
} from "lucide-react";
import { SiteHeader } from "@/components/SiteHeader";
import { ChatSidebar } from "@/components/ChatSidebar";
import { CitationDrawer } from "@/components/CitationDrawer";
import { CourseUploadModal } from "@/components/CourseUploadModal";
import {
  ChatSession,
  listSessions,
  createSession,
  getSession,
  sendSessionMessage,
  ContentUnit,
} from "@/lib/api";

interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{
    unit_id: string;
    source: string;
    label: string;
    open_url: string;
    location: {
      page?: number | null;
      slide?: number | null;
      timestamp?: string | null;
    };
    excerpt: string;
    diagram_caption?: string | null;
  }>;
  status?: "grounded" | "partial" | "refused";
  confidence?: number | null;
  claims?: Array<{
    text: string;
    supported: boolean;
    citations?: any[];
  }>;
  outside_knowledge?: string[];
  created_at?: string;
}

const STARTER_PROMPTS = [
  {
    icon: BookOpen,
    title: "Summarize Core Concepts",
    prompt: "What are the core concepts and fundamental topics covered in my uploaded course material?",
    tag: "Overview",
  },
  {
    icon: Sparkles,
    title: "Mathematical Proofs & Derivations",
    prompt: "Explain the key mathematical equations and step-by-step derivations found in the course slides.",
    tag: "Theory",
  },
  {
    icon: Layers,
    title: "Prerequisite Concept Map",
    prompt: "What prerequisite concepts should I master before moving to the advanced chapters in this course?",
    tag: "Graph",
  },
  {
    icon: GraduationCap,
    title: "Generate Practice Question",
    prompt: "Generate an adaptive practice question based on the most difficult concept in my uploaded notes.",
    tag: "Quiz",
  },
];

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [hindiMode, setHindiMode] = useState(false);
  const [showEvidenceInspector, setShowEvidenceInspector] = useState(false);
  const [allowOutsideKnowledge, setAllowOutsideKnowledge] = useState(false);
  const [activeCitation, setActiveCitation] = useState<any | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [latestAnswerData, setLatestAnswerData] = useState<any | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-collapse sidebar on initial mobile view
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setIsSidebarCollapsed(true);
    }
  }, []);

  // Auto-scroll to bottom of chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Load initial session on startup
  useEffect(() => {
    async function initSession() {
      try {
        const list = await listSessions("student_default");
        setSessions(list);
        if (list.length > 0) {
          const mostRecent = list[0];
          setCurrentSession(mostRecent);
          loadSessionMessages(mostRecent.id);
        } else {
          const newSess = await createSession("student_default", "New Chat");
          setCurrentSession(newSess);
          setSessions([newSess]);
          setMessages([]);
        }
      } catch (err) {
        console.error("Failed to initialize session:", err);
      }
    }
    initSession();
  }, []);

  // Load messages for a given session
  const loadSessionMessages = async (sessionId: string) => {
    try {
      const data = await getSession(sessionId);
      if (data && data.messages) {
        const formatted: MessageItem[] = data.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          citations: m.citations || [],
          created_at: m.created_at,
        }));
        setMessages(formatted);
        if (formatted.length > 0) {
          const lastAssistant = [...formatted].reverse().find((m) => m.role === "assistant");
          if (lastAssistant) {
            setLatestAnswerData(lastAssistant);
          }
        }
      }
    } catch (err) {
      console.error("Failed to load session messages:", err);
      setMessages([]);
    }
  };

  // Switch session
  const handleSelectSession = (sess: ChatSession) => {
    setCurrentSession(sess);
    loadSessionMessages(sess.id);
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setIsSidebarCollapsed(true);
    }
  };

  // Start new chat
  const handleNewChat = (newSess: ChatSession) => {
    setCurrentSession(newSess);
    setMessages([]);
    setLatestAnswerData(null);
    setSidebarRefresh((prev) => prev + 1);
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setIsSidebarCollapsed(true);
    }
  };

  // Send message
  const handleSend = async (customPrompt?: string) => {
    const textToSend = (customPrompt || input).trim();
    if (!textToSend || isLoading) return;

    let targetSessionId = currentSession?.id;

    if (!targetSessionId) {
      try {
        const created = await createSession("student_default", textToSend.slice(0, 40));
        targetSessionId = created.id;
        setCurrentSession(created);
        setSidebarRefresh((prev) => prev + 1);
      } catch {
        targetSessionId = `temp_${Date.now()}`;
      }
    }

    const userMsgId = `user_${Date.now()}`;
    const userMessage: MessageItem = {
      id: userMsgId,
      role: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsLoading(true);

    try {
      const promptPayload = hindiMode
        ? `${textToSend}\n\n[Please explain in Hindi (Devanagari script), keeping technical terms accessible].`
        : textToSend;

      const resp = await sendSessionMessage(
        targetSessionId,
        promptPayload,
        allowOutsideKnowledge,
        "student_default"
      );

      const assistantMsgId = `ast_${Date.now()}`;
      const assistantMessage: MessageItem = {
        id: assistantMsgId,
        role: "assistant",
        content: resp.text,
        citations: resp.citations || [],
        status: resp.status,
        confidence: resp.confidence,
        claims: resp.claims,
        outside_knowledge: resp.outside_knowledge,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLatestAnswerData(resp);
      setSidebarRefresh((prev) => prev + 1);
    } catch (err: any) {
      console.error("Chat error:", err);
      const errMsg: MessageItem = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content:
          "⚠️ Unable to connect to the Saarthi reasoning service. Please check that the backend is running (`uvicorn src.api.service:app`).",
        status: "refused",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for non-secure contexts (e.g. LAN IP HTTP access)
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
      }
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.warn("Failed to copy text:", err);
    }
  };

  const handleUploadSuccess = (unitsInput: ContentUnit | ContentUnit[]) => {
    setIsUploadModalOpen(false);
    setSidebarRefresh((prev) => prev + 1);

    const unitsArray = Array.isArray(unitsInput) ? unitsInput : [unitsInput];
    if (unitsArray.length === 0) return;

    const sourceNames = Array.from(new Set(unitsArray.map((u) => `\`${u.source_id}\``))).join(", ");
    const isMulti = unitsArray.length > 1;

    const tutorNotice: MessageItem = {
      id: `notice_${Date.now()}`,
      role: "assistant",
      content: `📥 **New Course Material${isMulti ? "s" : ""} Ingested (${unitsArray.length} file${isMulti ? "s" : ""}):** ${sourceNames} ${isMulti ? "have" : "has"} been indexed into the grounded knowledge store. You can now ask questions directly grounded in this material.`,
      citations: unitsArray.map((u) => ({
        unit_id: u.unit_id,
        source: u.source_id,
        label: u.location.slide
          ? `Slide ${u.location.slide}`
          : u.location.timestamp != null ? String(u.location.timestamp) : `Page ${u.location.page ?? 1}`,
        open_url: "#",
        location: {
          page: u.location.page,
          slide: u.location.slide,
          timestamp: typeof u.location.timestamp === "number"
            ? `@${u.location.timestamp}s`
            : u.location.timestamp,
        },
        excerpt: u.text,
        diagram_caption: u.image_caption,
      })),
      status: "grounded",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tutorNotice]);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-zinc-50 dark:bg-[#06090e] text-zinc-900 dark:text-zinc-100 font-sans antialiased transition-colors">
      {/* ─────────────────── Top Global Navigation Bar ─────────────────── */}
      <SiteHeader />

      {/* ─────────────────── Workbench Layout ─────────────────── */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* ChatGPT-style Collapsible & Responsive Sidebar */}
        <ChatSidebar
          currentSessionId={currentSession?.id}
          onSessionSelect={handleSelectSession}
          onNewChat={handleNewChat}
          studentId="student_default"
          hindiMode={hindiMode}
          onHindiModeToggle={() => setHindiMode((prev) => !prev)}
          showEvidenceInspector={showEvidenceInspector}
          onEvidenceToggle={() => setShowEvidenceInspector((prev) => !prev)}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
          refreshTrigger={sidebarRefresh}
        />

        {/* ─────────────────── Main Chat Window ─────────────────── */}
        <main className="flex-1 flex flex-col h-full overflow-hidden min-w-0 bg-zinc-50 dark:bg-[#070b14] relative">
          {/* Subheader: Session Title, Responsive Controls */}
          <header className="shrink-0 h-13 border-b border-zinc-200/80 dark:border-white/[0.06] bg-white/80 dark:bg-[#0c111e]/80 backdrop-blur-md px-3 sm:px-5 flex items-center justify-between z-10 transition-colors">
            <div className="flex items-center gap-2.5 min-w-0">
              <button
                onClick={() => setIsSidebarCollapsed((prev) => !prev)}
                className="p-1.5 rounded-xl text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.06] transition-all cursor-pointer"
                title={isSidebarCollapsed ? "Open sidebar" : "Close sidebar"}
              >
                {isSidebarCollapsed ? (
                  <Menu className="w-4 h-4 md:hidden" />
                ) : (
                  <PanelLeftClose className="w-4 h-4 hidden md:block" />
                )}
                {isSidebarCollapsed && <PanelLeftOpen className="w-4 h-4 hidden md:block" />}
              </button>

              <div className="flex items-center gap-2 min-w-0">
                <span className="font-semibold text-xs sm:text-sm text-zinc-800 dark:text-zinc-200 truncate max-w-[180px] sm:max-w-xs md:max-w-md">
                  {currentSession?.title || "New Chat"}
                </span>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Grounded
                </span>
              </div>
            </div>

            {/* Action Buttons Right */}
            <div className="flex items-center gap-1.5 sm:gap-2">
              {hindiMode && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full text-[11px] font-semibold bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-500/30">
                  🇮🇳 Hindi
                </span>
              )}

              <button
                onClick={() => setShowEvidenceInspector((prev) => !prev)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${showEvidenceInspector
                    ? "bg-indigo-50 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/30"
                    : "bg-zinc-100/80 dark:bg-white/[0.03] text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-white/[0.08] hover:text-zinc-950 dark:hover:text-white"
                  }`}
                title="Toggle Evidence Inspector"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Evidence</span>
              </button>

              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs shadow-indigo-600/20 transition-all cursor-pointer"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Upload Material</span>
                <span className="sm:hidden">Upload</span>
              </button>
            </div>
          </header>

          {/* Content Body: Chat Stream + Optional Sliding Evidence Inspector */}
          <div className="flex-1 flex overflow-hidden relative">
            {/* Scrollable Message List */}
            <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 flex flex-col justify-between">
              <div className="max-w-3xl w-full mx-auto space-y-5">
                {messages.length === 0 ? (
                  /* Hero Empty State */
                  <div className="py-8 sm:py-14 flex flex-col items-center text-center space-y-5 animate-fadeIn">
                    <div className="relative">
                      <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 text-white">
                        <Sparkles className="w-7 h-7 sm:w-8 sm:h-8" />
                      </div>
                      <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl blur-lg opacity-30 dark:opacity-40 -z-10" />
                    </div>

                    <div className="space-y-1.5 max-w-lg px-2">
                      <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-zinc-900 dark:text-white">
                        Namaste! I&apos;m Saarthi
                      </h2>
                      <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
                        Your verified adaptive tutor. Every explanation is strictly grounded in
                        your ingested course notes, slides, and video transcripts with zero hallucination.
                      </p>
                    </div>

                    {/* Starter Prompts Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-2xl pt-2">
                      {STARTER_PROMPTS.map((item, idx) => {
                        const Icon = item.icon;
                        return (
                          <button
                            key={idx}
                            onClick={() => handleSend(item.prompt)}
                            className="flex flex-col text-left p-3.5 rounded-2xl bg-white dark:bg-[#0e1424]/80 hover:bg-zinc-50 dark:hover:bg-[#141b30] border border-zinc-200/90 dark:border-white/[0.06] hover:border-indigo-400 dark:hover:border-indigo-500/40 transition-all group cursor-pointer shadow-2xs"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-500/20 transition-all">
                                <Icon className="w-4 h-4" />
                              </div>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-white/[0.04]">
                                {item.tag}
                              </span>
                            </div>
                            <h4 className="text-xs font-bold text-zinc-800 dark:text-zinc-200 group-hover:text-indigo-600 dark:group-hover:text-indigo-300 transition-colors">
                              {item.title}
                            </h4>
                            <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                              {item.prompt}
                            </p>
                          </button>
                        );
                      })}
                    </div>

                    {/* Upload Dropzone Hint */}
                    <div className="w-full max-w-2xl p-3.5 rounded-2xl border border-dashed border-zinc-300 dark:border-white/[0.12] bg-white/60 dark:bg-white/[0.01] flex flex-col sm:flex-row items-center justify-between gap-3 text-left">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shrink-0">
                          <UploadCloud className="w-5 h-5" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-zinc-900 dark:text-zinc-200">
                            Have new lecture documents?
                          </h4>
                          <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                            Upload lecture slides (PDF/PPTX) or videos to index them into your course knowledge base.
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => setIsUploadModalOpen(true)}
                        className="w-full sm:w-auto px-3 py-1.5 rounded-xl text-xs font-semibold bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-white/[0.08] transition-all cursor-pointer shrink-0 text-center"
                      >
                        Ingest Documents
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Active Message Stream */
                  messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col space-y-1.5 animate-fadeIn ${msg.role === "user" ? "items-end" : "items-start"
                        }`}
                    >
                      {/* Message Label */}
                      <div className="flex items-center gap-2 px-1">
                        {msg.role === "user" ? (
                          <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400">
                            You
                          </span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 dark:text-indigo-400">
                              <Sparkles className="w-3.5 h-3.5" />
                              Saarthi Tutor
                            </span>
                            {msg.confidence !== undefined && msg.confidence !== null && (
                              <span className="text-[10px] px-2 py-0.2 rounded-full font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                                {(msg.confidence * 100).toFixed(0)}% grounded
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Bubble */}
                      {msg.status === "refused" ? (
                        <div className="max-w-[90%] sm:max-w-[85%] p-4 rounded-2xl bg-rose-50 dark:bg-rose-500/[0.08] border border-rose-200 dark:border-rose-500/30 text-rose-900 dark:text-rose-200 shadow-2xs space-y-2">
                          <div className="flex items-center gap-2 font-bold text-xs text-rose-600 dark:text-rose-400">
                            <ShieldAlert className="w-4 h-4 shrink-0" />
                            <span>Strict Grounding Refusal (Zero Hallucination Policy)</span>
                          </div>
                          <p className="text-xs leading-relaxed whitespace-pre-line">
                            {msg.content}
                          </p>
                          <div className="pt-2 border-t border-rose-200 dark:border-rose-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-rose-700 dark:text-rose-300/80">
                            <span>This topic is missing from your uploaded course files.</span>
                            <button
                              onClick={() => {
                                setAllowOutsideKnowledge(true);
                                handleSend(msg.content);
                              }}
                              className="underline font-bold hover:text-rose-950 dark:hover:text-white cursor-pointer text-left sm:text-right"
                            >
                              Allow Outside Knowledge & Retry
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          className={`max-w-[92%] sm:max-w-[85%] p-3.5 sm:p-4 rounded-2xl text-xs sm:text-sm leading-relaxed space-y-3 relative group transition-colors ${msg.role === "user"
                              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/15 rounded-tr-xs"
                              : "bg-white dark:bg-[#0f1526] border border-zinc-200/90 dark:border-white/[0.08] text-zinc-800 dark:text-zinc-200 shadow-2xs rounded-tl-xs"
                            }`}
                        >
                          <div className="whitespace-pre-line leading-relaxed">{msg.content}</div>

                          {/* Grounding Citations */}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="pt-2.5 border-t border-zinc-100 dark:border-white/[0.06] space-y-1.5">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 block">
                                Grounded Sources:
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {msg.citations.map((c, cIdx) => (
                                  <button
                                    key={cIdx}
                                    onClick={() => setActiveCitation(c)}
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-semibold bg-indigo-50 hover:bg-indigo-100/80 dark:bg-indigo-500/10 dark:hover:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/25 transition-all cursor-pointer group"
                                    title={`View citation details from ${c.source}`}
                                  >
                                    {c.location?.slide ? (
                                      <FileText className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0" />
                                    ) : (
                                      <Video className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0" />
                                    )}
                                    <span className="truncate max-w-[120px] sm:max-w-[150px]">{c.source}</span>
                                    <span className="text-zinc-400">·</span>
                                    <span className="text-indigo-600 dark:text-indigo-400 font-bold">{c.label}</span>
                                    <ChevronRight className="w-3 h-3 text-indigo-400/70 group-hover:translate-x-0.5 transition-transform" />
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Copy Button */}
                          <div className="absolute right-2 bottom-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => copyToClipboard(msg.content, msg.id)}
                              className="p-1 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] text-zinc-500 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-white transition-all cursor-pointer"
                              title="Copy text"
                            >
                              {copiedId === msg.id ? (
                                <Check className="w-3.5 h-3.5 text-emerald-500" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}

                {/* Loading indicator */}
                {isLoading && (
                  <div className="flex flex-col space-y-1.5 items-start animate-fadeIn">
                    <div className="flex items-center gap-1.5 px-1">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-500 animate-spin" />
                      <span className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400">
                        Saarthi Grounding Engine
                      </span>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-white dark:bg-[#0f1526] border border-zinc-200/90 dark:border-white/[0.08] text-zinc-600 dark:text-zinc-300 text-xs flex items-center gap-2.5 shadow-2xs">
                      <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
                      <span>Retrieving hybrid vector chunks & mathematically verifying evidence...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Evidence Inspector Sliding Drawer */}
            {showEvidenceInspector && (
              <aside className="w-80 lg:w-96 shrink-0 border-l border-zinc-200/90 dark:border-white/[0.08] bg-white/95 dark:bg-[#0c111e]/95 backdrop-blur-md flex flex-col h-full z-20 animate-slideLeft">
                <div className="shrink-0 p-3.5 border-b border-zinc-200/80 dark:border-white/[0.06] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                      Evidence Inspector
                    </h3>
                  </div>
                  <button
                    onClick={() => setShowEvidenceInspector(false)}
                    className="p-1 rounded-lg text-zinc-500 hover:text-zinc-950 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.06] transition-all cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5 text-xs">
                  {/* Confidence Breakdown Card */}
                  <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500 dark:text-zinc-400 font-medium">Retriever</span>
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold border border-emerald-500/20">
                        Hybrid Vector Search
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500 dark:text-zinc-400 font-medium">Confidence</span>
                      <span className="font-bold text-zinc-900 dark:text-zinc-100">
                        {latestAnswerData?.confidence
                          ? `${(latestAnswerData.confidence * 100).toFixed(1)}%`
                          : "High (Verified)"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500 dark:text-zinc-400 font-medium">Outside Knowledge</span>
                      <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                        {allowOutsideKnowledge ? "Permitted" : "Strictly Blocked"}
                      </span>
                    </div>
                  </div>

                  {/* Retrieved Chunks */}
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      Retrieved Chunks ({latestAnswerData?.citations?.length || 0})
                    </h4>

                    {latestAnswerData?.citations && latestAnswerData.citations.length > 0 ? (
                      latestAnswerData.citations.map((c: any, i: number) => (
                        <div
                          key={i}
                          onClick={() => setActiveCitation(c)}
                          className="p-3 rounded-xl bg-zinc-50 hover:bg-indigo-50/70 dark:bg-white/[0.02] dark:hover:bg-indigo-500/[0.06] border border-zinc-200/80 hover:border-indigo-300 dark:border-white/[0.06] dark:hover:border-indigo-500/30 transition-all cursor-pointer space-y-1"
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-indigo-600 dark:text-indigo-300">{c.source}</span>
                            <span className="text-zinc-500 dark:text-zinc-400 font-mono text-[10px]">{c.label}</span>
                          </div>
                          <p className="text-[11px] text-zinc-600 dark:text-zinc-400 line-clamp-3 leading-relaxed">
                            {c.excerpt}
                          </p>
                          {c.diagram_caption && (
                            <div className="pt-1 border-t border-zinc-200/60 dark:border-white/[0.04] text-[10px] text-amber-700 dark:text-amber-300/90 font-medium">
                              🖼️ {c.diagram_caption}
                            </div>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="p-4 rounded-xl border border-dashed border-zinc-200 dark:border-white/[0.08] text-center text-zinc-500 text-xs">
                        Ask a question to inspect live retrieved vector chunks.
                      </div>
                    )}
                  </div>

                  {/* Verified Atomic Claims */}
                  {latestAnswerData?.claims && latestAnswerData.claims.length > 0 && (
                    <div className="space-y-2 pt-2 border-t border-zinc-200/80 dark:border-white/[0.06]">
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                        Verified Atomic Claims
                      </h4>
                      <div className="space-y-1.5">
                        {latestAnswerData.claims.map((cl: any, idx: number) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded-lg bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/60 dark:border-white/[0.04] flex items-start gap-2"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                            <span className="text-[11px] text-zinc-700 dark:text-zinc-300 leading-relaxed">
                              {cl.text}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </aside>
            )}
          </div>

          {/* Sticky Input Composer */}
          <div className="shrink-0 p-3 sm:p-4 max-w-3xl w-full mx-auto relative z-10">
            <div className="relative rounded-2xl bg-white dark:bg-[#0f1526] border border-zinc-200 dark:border-white/[0.1] focus-within:border-indigo-500 dark:focus-within:border-indigo-500/70 shadow-lg shadow-black/5 dark:shadow-black/40 transition-all p-2 flex flex-col space-y-1.5">
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={
                  hindiMode
                    ? "पाठ्यक्रम सामग्री से कोई भी प्रश्न पूछें (Ask in Hindi or English)..."
                    : "Ask anything from your uploaded lecture notes or video transcripts..."
                }
                className="w-full bg-transparent resize-none text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none px-2.5 py-1.5 max-h-40 leading-relaxed font-sans"
              />

              {/* Bottom Control Bar */}
              <div className="flex items-center justify-between px-1.5 pt-1 border-t border-zinc-100 dark:border-white/[0.04]">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <button
                    type="button"
                    onClick={() => setIsUploadModalOpen(true)}
                    className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/[0.06] transition-all cursor-pointer flex items-center gap-1.5 text-xs font-semibold"
                    title="Upload course PDF, PPTX or video"
                  >
                    <Paperclip className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline text-[11px]">Attach Material</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setAllowOutsideKnowledge((prev) => !prev)}
                    className={`px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${allowOutsideKnowledge
                        ? "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300 border border-amber-300 dark:border-amber-500/25"
                        : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/[0.04]"
                      }`}
                    title="When enabled, allows general AI reasoning when material is missing"
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${allowOutsideKnowledge ? "bg-amber-500" : "bg-zinc-400 dark:bg-zinc-600"
                        }`}
                    />
                    <span>Outside Knowledge</span>
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 text-white transition-all shadow-xs shadow-indigo-600/20 cursor-pointer disabled:cursor-not-allowed"
                  title="Send message (Enter)"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="text-center mt-1.5">
              <p className="text-[10px] text-zinc-500 dark:text-zinc-500 font-medium">
                Grounded in uploaded course materials with verified citations.
              </p>
            </div>
          </div>
        </main>

        {/* Grounding Citation Drawer */}
        <CitationDrawer
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />

        {/* Course Material Upload Modal */}
        <CourseUploadModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          onUploadSuccess={handleUploadSuccess}
        />
      </div>
    </div>
  );
}
