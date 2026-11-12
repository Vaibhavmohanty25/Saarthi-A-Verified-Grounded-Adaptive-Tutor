"use client";

import React, { useState, useRef } from "react";
import {
  X,
  FileText,
  Video,
  Image as ImageIcon,
  Layers,
  FileCode,
  Download,
  ExternalLink,
  GitBranch,
  BookOpen,
  Sparkles,
  ChevronRight,
  Maximize2,
  Play,
  Clock,
} from "lucide-react";
import { UploadedMaterial, getApiBaseUrl } from "@/lib/api";

interface MediaPreviewModalProps {
  material: UploadedMaterial | null;
  isOpen: boolean;
  onClose: () => void;
  onSelectConcept?: (conceptId: string) => void;
}

export function MediaPreviewModal({
  material,
  isOpen,
  onClose,
  onSelectConcept,
}: MediaPreviewModalProps) {
  const [activeTab, setActiveTab] = useState<"preview" | "chunks" | "concepts">("preview");
  const videoRef = useRef<HTMLVideoElement>(null);

  if (!isOpen || !material) return null;

  const apiBase = getApiBaseUrl();
  const fileUrl = `${apiBase}${material.download_url}`;
  const isLegacyPresentation = material.file_type === "ppt" || material.filename.toLowerCase().endsWith(".ppt");

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function getCategoryInfo(type: string) {
    switch (type) {
      case "pdf":
        return {
          label: "PDF Textbook / Notes",
          icon: FileText,
          badgeClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
        };
      case "ppt":
      case "pptx":
        return {
          label: type === "ppt" ? "Legacy PowerPoint (.ppt)" : "PPTX Lecture Slides",
          icon: Layers,
          badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
        };
      case "video":
        return {
          label: "Lecture Video Recording",
          icon: Video,
          badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        };
      case "image":
        return {
          label: "Educational Diagram",
          icon: ImageIcon,
          badgeClass: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
        };
      default:
        return {
          label: "Course Document",
          icon: FileCode,
          badgeClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
        };
    }
  }

  const catInfo = getCategoryInfo(isLegacyPresentation ? "ppt" : material.file_type);
  const CatIcon = catInfo.icon;

  const handleSeekVideo = (timestamp?: string | number | null, seconds?: number | null) => {
    if (!videoRef.current) return;
    let target = seconds ?? (typeof timestamp === "number" ? timestamp : undefined);
    if (target === undefined && typeof timestamp === "string") {
      const clean = timestamp.replace("@", "").replace(/s$/i, "").trim();
      const parts = clean.split(":").map(Number);
      if (parts.length === 3 && !parts.some(isNaN)) {
        target = parts[0] * 3600 + parts[1] * 60 + parts[2];
      } else if (parts.length === 2 && !parts.some(isNaN)) {
        target = parts[0] * 60 + parts[1];
      } else {
        const num = parseFloat(clean);
        if (!isNaN(num)) target = num;
      }
    }
    if (target !== undefined && !isNaN(target)) {
      videoRef.current.currentTime = target;
      const playPromise = videoRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Autoplay notice:", err);
        });
      }
      videoRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/60 dark:bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.12] rounded-3xl shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
        
        {/* Glow ambient background */}
        <div className="absolute top-0 right-1/4 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-zinc-200/80 dark:border-white/[0.08] flex items-start justify-between gap-3 shrink-0 bg-zinc-50/50 dark:bg-white/[0.01]">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 rounded-2xl bg-indigo-500/10 dark:bg-indigo-500/15 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400 shrink-0">
              <CatIcon className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white truncate" title={material.filename}>
                  {material.filename}
                </h3>
                <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${catInfo.badgeClass}`}>
                  {catInfo.label}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                <span>{formatBytes(material.size_bytes)}</span>
                <span>•</span>
                <span>{material.units_count} extracted knowledge units</span>
                {material.linked_concepts.length > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-indigo-600 dark:text-indigo-400 font-medium">
                      Grounds {material.linked_concepts.length} concept{material.linked_concepts.length > 1 ? "s" : ""}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.05] dark:hover:bg-white/[0.1] text-zinc-600 dark:text-zinc-300 transition-colors"
              title="Open raw file in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.05] dark:hover:bg-white/[0.1] text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors cursor-pointer"
              title="Close preview"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* View Navigation Tabs */}
        <div className="flex items-center gap-1 px-4 sm:px-6 pt-3 border-b border-zinc-200/80 dark:border-white/[0.06] bg-zinc-50/30 dark:bg-white/[0.01] shrink-0">
          <button
            onClick={() => setActiveTab("preview")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "preview"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Interactive Media Preview</span>
          </button>
          <button
            onClick={() => setActiveTab("chunks")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "chunks"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Extracted Units ({material.sample_units.length})</span>
          </button>
          <button
            onClick={() => setActiveTab("concepts")}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "concepts"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span>Grounded DAG Concepts ({material.linked_concepts.length})</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 min-h-[350px]">
          {isLegacyPresentation && material.units_count === 0 && (
            <p className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
              Saarthi requires a .pptx to extract slide text and concepts. Open the .ppt in PowerPoint, save it as a PowerPoint Presentation (.pptx), and upload the saved copy.
            </p>
          )}
          {activeTab === "preview" && (
            <div className="h-full flex flex-col space-y-4">
              {/* PDF Viewer */}
              {material.file_type === "pdf" && (
                <div className="w-full h-[520px] rounded-2xl overflow-hidden border border-zinc-200 dark:border-white/[0.08] bg-zinc-100 dark:bg-black/40 shadow-inner">
                  <iframe
                    src={fileUrl}
                    className="w-full h-full"
                    title={`Preview of ${material.filename}`}
                  />
                </div>
              )}

              {/* Image Preview */}
              {material.file_type === "image" && (
                <div className="flex flex-col items-center justify-center p-4 bg-zinc-50 dark:bg-black/30 rounded-2xl border border-zinc-200 dark:border-white/[0.08]">
                  <img
                    src={fileUrl}
                    alt={material.filename}
                    className="max-h-[460px] max-w-full rounded-xl object-contain shadow-lg"
                  />
                  {material.sample_units[0]?.image_caption && (
                    <div className="mt-4 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs text-purple-700 dark:text-purple-300 max-w-xl text-center">
                      <span className="font-bold">Vision Caption:</span> {material.sample_units[0].image_caption}
                    </div>
                  )}
                </div>
              )}

              {/* Video Player & Interactive Segment Navigator */}
              {material.file_type === "video" && (
                <div className="space-y-4">
                  <div className="w-full rounded-2xl overflow-hidden border border-zinc-200 dark:border-white/[0.08] bg-black shadow-lg">
                    <video
                      ref={videoRef}
                      controls
                      preload="metadata"
                      src={fileUrl}
                      className="w-full max-h-[460px] bg-black"
                    >
                      Your browser does not support the video tag.
                    </video>
                  </div>

                  {/* Segment Navigation */}
                  <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.08] space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-emerald-500" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-900 dark:text-white">
                          Video Segments & Timestamps ({material.sample_units.length})
                        </h4>
                      </div>
                      <span className="text-[11px] text-zinc-500">
                        Click any segment to jump and play video
                      </span>
                    </div>

                    {material.sample_units.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-[320px] overflow-y-auto pr-1">
                        {material.sample_units.map((unit, idx) => (
                          <div
                            key={unit.unit_id || idx}
                            onClick={() =>
                              handleSeekVideo(
                                unit.location?.timestamp,
                                (unit.location as any)?.seconds
                              )
                            }
                            className="p-3 rounded-xl bg-white dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.06] hover:border-emerald-500/50 hover:bg-emerald-500/[0.03] transition-all cursor-pointer flex flex-col justify-between group shadow-2xs"
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                                <Play className="w-2.5 h-2.5 fill-current" />
                                <span>{unit.location?.timestamp || `@${idx * 45}s`}</span>
                              </span>
                              <span className="text-[10px] font-mono text-zinc-400">
                                {unit.unit_id}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed line-clamp-3">
                              {unit.text}
                            </p>
                            <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-zinc-100 dark:border-white/[0.04]">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSeekVideo(
                                    unit.location?.timestamp,
                                    (unit.location as any)?.seconds
                                  );
                                }}
                                className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold shadow-2xs transition-all flex items-center gap-1 cursor-pointer"
                              >
                                <Play className="w-2.5 h-2.5 fill-current" />
                                <span>Play this segment</span>
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-4 text-center text-xs text-zinc-500">
                        No timestamped segments found. The audio transcription will automatically populate when processed.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* PPTX Presentation Slide Cards */}
              {(isLegacyPresentation || material.file_type === "pptx") && (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-200 flex items-center justify-between">
                    <span>
                      {material.units_count > 0 ? "Showing extracted slide text." : "Download the original presentation."}
                    </span>
                    <a
                      href={fileUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1 rounded-lg bg-amber-600 text-white font-semibold flex items-center gap-1 hover:bg-amber-700 transition-colors shrink-0"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>{isLegacyPresentation ? "Download PPT" : "Download PPTX"}</span>
                    </a>
                  </div>

                  {material.sample_units.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {material.sample_units.map((unit, idx) => (
                        <div
                          key={unit.unit_id || idx}
                          className="p-4 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08] shadow-xs flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                                {unit.location?.slide ? `Slide ${unit.location.slide}` : `Slide ${idx + 1}`}
                              </span>
                              <span className="text-[10px] font-mono text-zinc-400">
                                {unit.unit_id}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed line-clamp-6 whitespace-pre-line">
                              {unit.text}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-xs text-zinc-500">
                      No extracted slide text found for this file.
                    </div>
                  )}
                </div>
              )}

              {/* Text / Document Preview */}
              {material.file_type === "document" && (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-800 dark:text-blue-200 flex items-center justify-between">
                    <span>
                      📄 Course document content. Inspect extracted knowledge sections or download the original file.
                    </span>
                    <a
                      href={fileUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1 rounded-lg bg-blue-600 text-white font-semibold flex items-center gap-1 hover:bg-blue-700 transition-colors shrink-0"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download File</span>
                    </a>
                  </div>

                  {material.sample_units.length > 0 ? (
                    <div className="space-y-3">
                      {material.sample_units.map((unit, idx) => (
                        <div
                          key={unit.unit_id || idx}
                          className="p-4 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08] shadow-xs"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/15 text-blue-700 dark:text-blue-300 border border-blue-500/30">
                              Section {unit.location?.page || idx + 1}
                            </span>
                            <span className="text-[10px] font-mono text-zinc-400">
                              {unit.unit_id}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono bg-zinc-100/50 dark:bg-black/20 p-3 rounded-xl">
                            {unit.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-xs text-zinc-500">
                      No text units extracted for this document.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Extracted Chunks Tab */}
          {activeTab === "chunks" && (
            <div className="space-y-3">
              {material.sample_units.length === 0 && (
                <p className="p-8 text-center text-xs text-zinc-500">No extracted units are available for this file.</p>
              )}
              {material.sample_units.map((unit, idx) => (
                <div
                  key={unit.unit_id || idx}
                  className="p-3.5 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08]"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 font-mono">
                        {unit.location?.slide
                          ? `Slide ${unit.location.slide}`
                          : unit.location?.page
                          ? `Page ${unit.location.page}`
                          : unit.location?.timestamp || `Unit ${idx + 1}`}
                      </span>
                      <span className="text-[11px] font-mono text-zinc-400">
                        {unit.unit_id}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-zinc-800 dark:text-zinc-200 leading-relaxed whitespace-pre-line">
                    {unit.text}
                  </p>
                  {unit.image_caption && (
                    <div className="mt-2 text-[11px] text-purple-600 dark:text-purple-400 italic bg-purple-500/10 p-2 rounded-lg">
                      Diagram annotation: {unit.image_caption}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Grounded Concepts Tab */}
          {activeTab === "concepts" && (
            <div className="space-y-3">
              {material.linked_concepts.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {material.linked_concepts.map((c) => (
                    <div
                      key={c.concept_id}
                      className="p-4 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08] flex items-center justify-between group hover:border-indigo-500/40 transition-all shadow-xs"
                    >
                      <div>
                        <span className="text-[10px] font-mono uppercase text-zinc-400 block mb-0.5">
                          {c.topic}
                        </span>
                        <h4 className="text-sm font-bold text-zinc-900 dark:text-white">
                          {c.name}
                        </h4>
                        <span className="text-[11px] text-zinc-500 font-mono">
                          {c.concept_id}
                        </span>
                      </div>

                      {onSelectConcept && (
                        <button
                          onClick={() => {
                            onSelectConcept(c.concept_id);
                            onClose();
                          }}
                          className="px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-600 hover:text-white dark:hover:bg-indigo-500 transition-all text-xs font-semibold flex items-center gap-1 cursor-pointer"
                        >
                          <span>View in DAG</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-xs text-zinc-500">
                  No concepts are linked to this file.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 sm:p-4 border-t border-zinc-200/80 dark:border-white/[0.08] flex items-center justify-between text-xs text-zinc-500 shrink-0 bg-zinc-50/50 dark:bg-white/[0.01]">
          <span>{material.units_count > 0 ? "Available for grounded chat" : "No extracted content"}</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-full bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200 font-semibold transition-all cursor-pointer shadow-xs"
          >
            Done
          </button>
        </div>

      </div>
    </div>
  );
}
