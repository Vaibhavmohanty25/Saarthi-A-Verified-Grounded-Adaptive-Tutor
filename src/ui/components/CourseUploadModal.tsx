"use client";

import React, { useState, useRef } from "react";
import {
  X,
  UploadCloud,
  FileText,
  Video,
  Image as ImageIcon,
  CheckCircle2,
  Loader2,
  Sparkles,
  Layers,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Trash2,
  Plus,
  FileCode,
} from "lucide-react";
import { ContentUnit, uploadCourseFiles } from "@/lib/api";

interface CourseUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (units: ContentUnit[]) => void;
}

type FileCategory = "video" | "pdf" | "pptx" | "image" | "document";

function getFileCategory(file: File): FileCategory {
  const name = file.name.toLowerCase();
  if (file.type.startsWith("video/") || /\.(mp4|mov|webm|avi|mkv)$/i.test(name)) return "video";
  if (name.endsWith(".pdf") || file.type === "application/pdf") return "pdf";
  if (/\.(pptx|ppt)$/i.test(name)) return "pptx";
  if (file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|svg)$/i.test(name)) return "image";
  return "document";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getCategoryBadge(category: FileCategory) {
  switch (category) {
    case "video":
      return {
        label: "MP4 Video",
        icon: Video,
        colorClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
      };
    case "pdf":
      return {
        label: "PDF Doc",
        icon: FileText,
        colorClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
      };
    case "pptx":
      return {
        label: "PPTX Slides",
        icon: Layers,
        colorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
      };
    case "image":
      return {
        label: "Diagram",
        icon: ImageIcon,
        colorClass: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
      };
    default:
      return {
        label: "Document",
        icon: FileCode,
        colorClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
      };
  }
}

export function CourseUploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
}: CourseUploadModalProps) {
  const [dragActive, setDragActive] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [pipelineStage, setPipelineStage] = useState<string>("");
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleAddFiles = (incomingList: FileList | File[]) => {
    setErrorNotice(null);
    const newFiles = Array.from(incomingList);
    if (newFiles.length === 0) return;

    const currentHasVideo = stagedFiles.some((f) => getFileCategory(f) === "video");
    const incomingHasVideo = newFiles.some((f) => getFileCategory(f) === "video");

    // Rule 1: Video must be standalone by itself
    if (incomingHasVideo) {
      if (newFiles.length > 1) {
        setErrorNotice(
          "Videos require intensive Whisper audio speech-to-text and keyframe extraction, and must be uploaded individually (1 video by itself)."
        );
        return;
      }
      if (stagedFiles.length > 0) {
        setErrorNotice(
          "Videos must be uploaded individually. Cannot mix video with documents or images."
        );
        return;
      }
      // Exactly 1 standalone video
      setStagedFiles([newFiles[0]]);
      return;
    }

    if (currentHasVideo) {
      setErrorNotice(
        "A video is currently staged. Videos must be uploaded individually. Remove the video to upload documents/images."
      );
      return;
    }

    // Rule 2: 10 files max limit
    const totalCount = stagedFiles.length + newFiles.length;
    if (totalCount > 10) {
      const allowed = 10 - stagedFiles.length;
      if (allowed <= 0) {
        setErrorNotice("Maximum batch limit of 10 files reached. Remove files to add more.");
        return;
      }
      setErrorNotice(
        `Maximum limit is 10 files. Added ${allowed} file(s), remaining were skipped.`
      );
      setStagedFiles((prev) => [...prev, ...newFiles.slice(0, allowed)]);
      return;
    }

    setStagedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleAddFiles(e.target.files);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveFile = (index: number) => {
    setErrorNotice(null);
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const startIngestion = async () => {
    if (stagedFiles.length === 0 || isProcessing) return;
    setIsProcessing(true);
    setProgress(15);
    setPipelineStage("Parsing document structure & validating media formats...");

    const hasVideo = stagedFiles.some((f) => getFileCategory(f) === "video");

    const timer1 = setTimeout(() => {
      setProgress(40);
      setPipelineStage(
        hasVideo
          ? "Aligning timestamps via speech-to-text audio models..."
          : `Extracting text chunks, diagram captions & formulas across ${stagedFiles.length} file(s)...`
      );
    }, 700);

    const timer2 = setTimeout(() => {
      setProgress(75);
      setPipelineStage("Synthesizing concept graph nodes & indexing into hybrid vector store...");
    }, 1500);

    try {
      const res = await uploadCourseFiles(stagedFiles);
      clearTimeout(timer1);
      clearTimeout(timer2);
      setProgress(100);
      setPipelineStage(
        `Ingestion Complete: ${res.units_created || stagedFiles.length} units indexed!`
      );

      setTimeout(() => {
        onUploadSuccess(res.sample_units);
        setIsProcessing(false);
        setStagedFiles([]);
        setProgress(0);
        onClose();
      }, 700);
    } catch (err) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setErrorNotice(err instanceof Error ? err.message : "Course upload failed.");
      setIsProcessing(false);
      setProgress(0);
      setPipelineStage("");
    }
  };

  const isVideoStaged = stagedFiles.some((f) => getFileCategory(f) === "video");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 dark:bg-black/80 backdrop-blur-md transition-all">
      <div className="relative w-full max-w-xl bg-white dark:bg-[#0c111c] border border-zinc-200 dark:border-white/[0.12] rounded-3xl shadow-2xl p-6 sm:p-7 overflow-hidden">
        {/* Glow ambient background */}
        <div className="absolute top-0 right-1/4 w-56 h-56 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-zinc-200/80 dark:border-white/[0.08]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-indigo-500/10 dark:bg-indigo-500/15 border border-indigo-500/20 dark:border-indigo-500/25 text-indigo-600 dark:text-indigo-400">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-zinc-900 dark:text-white">
                  Upload Course Materials
                </h3>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 dark:border-emerald-500/30">
                  Multimodal Ingestion
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Batch ingest up to 10 files (PDF, PPTX, Images) or 1 standalone video into the grounded vector store.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-1.5 rounded-xl bg-zinc-100 hover:bg-zinc-200 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-all cursor-pointer disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Validation Error Banner */}
        {errorNotice && (
          <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5 text-xs text-amber-700 dark:text-amber-300 animate-in fade-in duration-200">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">{errorNotice}</div>
            <button
              onClick={() => setErrorNotice(null)}
              className="text-amber-600 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-200 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Body / Staging Area */}
        <div className="py-4 space-y-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileChange}
            accept=".pdf,.pptx,.ppt,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp,.txt,.md"
            className="hidden"
          />

          {!isProcessing ? (
            <>
              {stagedFiles.length === 0 ? (
                /* Empty Dropzone */
                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`p-7 rounded-2xl border-2 border-dashed transition-all flex flex-col items-center justify-center text-center cursor-pointer ${
                    dragActive
                      ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20"
                      : "border-zinc-300 dark:border-white/[0.12] bg-zinc-50/50 dark:bg-white/[0.02] hover:bg-zinc-100/70 dark:hover:bg-white/[0.04] hover:border-zinc-400 dark:hover:border-white/[0.2]"
                  }`}
                >
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-3 shadow-sm">
                    <UploadCloud className="w-6 h-6" />
                  </div>

                  <h4 className="text-sm font-bold text-zinc-900 dark:text-white mb-1">
                    Drop up to 10 course files here, or{" "}
                    <span className="text-indigo-600 dark:text-indigo-400 underline">browse</span>
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-sm mb-4">
                    Mix PDF textbooks, PPTX lecture slides, and diagram images. (Videos must be uploaded individually).
                  </p>

                  <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] font-semibold text-zinc-500 dark:text-zinc-400">
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-zinc-200/60 dark:bg-white/[0.06]">
                      <FileText className="w-3 h-3 text-rose-500" /> PDF / PPTX
                    </span>
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-zinc-200/60 dark:bg-white/[0.06]">
                      <ImageIcon className="w-3 h-3 text-purple-500" /> Diagrams & Images
                    </span>
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-zinc-200/60 dark:bg-white/[0.06]">
                      <Video className="w-3 h-3 text-emerald-500" /> Video (Single)
                    </span>
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-bold border border-indigo-500/20">
                      Up to 10 Files
                    </span>
                  </div>
                </div>
              ) : (
                /* Staged Files Queue */
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    <div className="flex items-center gap-2">
                      <span>Staged Files:</span>
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                        isVideoStaged
                          ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
                          : stagedFiles.length === 10
                          ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30"
                          : "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30"
                      }`}>
                        {isVideoStaged ? "1 Video (Individual Mode)" : `${stagedFiles.length} of 10 files`}
                      </span>
                    </div>

                    <button
                      onClick={() => setStagedFiles([])}
                      className="text-[11px] text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors cursor-pointer"
                    >
                      Clear all
                    </button>
                  </div>

                  {/* Scrollable List */}
                  <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                    {stagedFiles.map((file, idx) => {
                      const category = getFileCategory(file);
                      const badge = getCategoryBadge(category);
                      const Icon = badge.icon;

                      return (
                        <div
                          key={`${file.name}-${idx}`}
                          className="p-2.5 rounded-xl bg-zinc-50 dark:bg-white/[0.03] border border-zinc-200/80 dark:border-white/[0.08] flex items-center justify-between gap-3 text-xs"
                        >
                          <div className="flex items-center gap-2.5 min-w-0 flex-1">
                            <span
                              className={`px-2 py-0.5 rounded-md text-[10px] font-bold border flex items-center gap-1 shrink-0 ${badge.colorClass}`}
                            >
                              <Icon className="w-3 h-3" />
                              {badge.label}
                            </span>
                            <span
                              className="font-medium text-zinc-900 dark:text-zinc-100 truncate"
                              title={file.name}
                            >
                              {file.name}
                            </span>
                            <span className="text-[11px] text-zinc-400 shrink-0 font-mono">
                              ({formatFileSize(file.size)})
                            </span>
                          </div>

                          <button
                            onClick={() => handleRemoveFile(idx)}
                            className="p-1 rounded-lg text-zinc-400 hover:text-rose-600 hover:bg-rose-500/10 transition-colors cursor-pointer shrink-0"
                            title="Remove file"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>

                  {/* Add more files row if under limit and not in video mode */}
                  {!isVideoStaged && stagedFiles.length < 10 && (
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="w-full py-2 px-3 rounded-xl border border-dashed border-zinc-300 dark:border-white/[0.12] hover:border-indigo-500 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add more documents or diagrams ({10 - stagedFiles.length} slots left)</span>
                    </button>
                  )}
                </div>
              )}
            </>
          ) : (
            /* Processing Progress */
            <div className="p-6 rounded-2xl bg-zinc-50 dark:bg-white/[0.02] border border-zinc-200 dark:border-white/[0.08] space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                    <Loader2 className="w-5 h-5 animate-spin" />
                  </div>
                  <div>
                    <h5 className="text-xs font-bold text-zinc-900 dark:text-white">
                      Processing {stagedFiles.length} material{stagedFiles.length > 1 ? "s" : ""}
                    </h5>
                    <span className="text-[11px] text-indigo-600 dark:text-indigo-400 font-medium">
                      {pipelineStage}
                    </span>
                  </div>
                </div>
                <span className="text-sm font-extrabold text-indigo-600 dark:text-indigo-400">
                  {progress}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-zinc-200 dark:bg-white/[0.08] h-2 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <div className="grid grid-cols-3 gap-2 pt-1 text-[10px] text-zinc-500 dark:text-zinc-400 font-semibold">
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1 ${
                    progress >= 30
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                      : "bg-transparent border-transparent"
                  }`}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Text & Vision</span>
                </div>
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1 ${
                    progress >= 60
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                      : "bg-transparent border-transparent"
                  }`}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Graph Sync</span>
                </div>
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1 ${
                    progress >= 100
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                      : "bg-transparent border-transparent"
                  }`}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Vector Stored</span>
                </div>
              </div>
            </div>
          )}

          {/* Feature Highlights */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="p-3 rounded-xl bg-zinc-50/80 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] text-xs">
              <span className="font-bold text-zinc-900 dark:text-white mb-0.5 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-indigo-500" /> Multi-Type Ingestion
              </span>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Mix PDF textbooks, PPTX slide decks, and diagrams together into one batch.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-zinc-50/80 dark:bg-white/[0.02] border border-zinc-200/80 dark:border-white/[0.06] text-xs">
              <span className="font-bold text-zinc-900 dark:text-white mb-0.5 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3 text-emerald-500" /> Isolated Video Rule
              </span>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Videos run specialized Whisper + keyframe extraction and are processed individually.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3.5 border-t border-zinc-200/80 dark:border-white/[0.08] flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
          <span>Max 10 files · Up to 500MB total</span>
          <div className="flex items-center gap-2">
            {stagedFiles.length === 0 ? (
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isProcessing}
                className="px-4 py-2 rounded-full bg-black text-white hover:bg-zinc-800 dark:bg-indigo-600 dark:hover:bg-indigo-500 transition-all font-semibold cursor-pointer disabled:opacity-40 shadow-sm"
              >
                Browse Files
              </button>
            ) : (
              <button
                onClick={startIngestion}
                disabled={isProcessing}
                className="px-5 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white transition-all font-semibold cursor-pointer disabled:opacity-40 shadow-sm flex items-center gap-1.5"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Ingesting...</span>
                  </>
                ) : (
                  <>
                    <span>Ingest {stagedFiles.length} Material{stagedFiles.length > 1 ? "s" : ""}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
