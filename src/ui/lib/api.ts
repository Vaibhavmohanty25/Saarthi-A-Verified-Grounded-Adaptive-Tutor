export interface SourceLocation {
  page?: number | null;
  slide?: number | null;
  timestamp?: string | number | null;
  seconds?: number | null;
}

export interface ContentUnit {
  unit_id: string;
  source_id: string;
  source_type: string;
  location: SourceLocation;
  text: string;
  image_caption?: string | null;
}

export interface UploadedMaterial {
  filename: string;
  size_bytes: number;
  file_type: string;
  modified_at: string;
  download_url: string;
  units_count: number;
  linked_concepts: { concept_id: string; name: string; topic: string }[];
  sample_units: Omit<ContentUnit, "source_id" | "source_type">[];
}

export interface ChatSession {
  id: string;
  student_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Citation {
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
}

interface SessionMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  created_at: string;
}

interface SessionAnswer {
  text: string;
  status: "grounded" | "partial" | "refused";
  confidence: number | null;
  mode: string | null;
  citations: Citation[];
  claims: { text: string; supported: boolean }[];
  outside_knowledge: string[];
}

export interface CompletedQuiz {
  id: string;
  topic: string;
  score: number;
  total: number;
  completed_at: string;
}

export interface GraphNode {
  id: string;
  name: string;
  topic: string;
  prerequisites: string[];
  evidence_count: number;
  assessment_available?: boolean;
  evidence_units: string[];
  evidence_details?: Omit<ContentUnit, "source_type">[];
  description: string;
  keyTakeaways: string[];
}

export interface QuizQuestion {
  q_id: string;
  attempt_id?: string;
  concept_id: string;
  topic: string;
  source_location: SourceLocation;
  difficulty: number;
  type: "mcq" | "numeric" | "short";
  stem: string;
  options: string[] | null;
  verified: boolean;
  verifier_agreement: number;
}

export interface RagasMetrics {
  faithfulness?: number;
  answer_relevancy?: number;
  context_precision?: number;
  context_recall?: number;
  refusal_accuracy?: number;
  refusal_precision?: number;
  verifier_agreement?: number;
}

export interface AblationPoint {
  session: string;
  random: number;
  adaptive: number;
}

interface AblationResult {
  sessions: number[];
  learning_curves: AblationPoint[];
  final_random: string;
  final_adaptive: string;
  net_gain_percentage: string;
  p_value: string;
  sample_size: string;
}

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, options);
  if (!response.ok) {
    const body: { detail?: unknown } | null = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new Error(`Saarthi API ${response.status}${detail ? ` (${detail})` : ""}`);
  }
  return response.json();
}

function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function forStudent(path: string, studentId: string): string {
  return `${path}?${new URLSearchParams({ student_id: studentId })}`;
}

export function listSessions(studentId = "student_default") {
  return request<ChatSession[]>(forStudent("/sessions", studentId));
}

export function createSession(studentId = "student_default", title = "New Chat") {
  return post<ChatSession>("/sessions", { student_id: studentId, title });
}

export function getSession(sessionId: string, studentId = "student_default") {
  return request<{ session: ChatSession; messages: SessionMessage[] }>(
    forStudent(`/sessions/${encodeURIComponent(sessionId)}`, studentId),
  );
}

export function deleteSession(sessionId: string, studentId = "student_default") {
  return request<{ status: string }>(forStudent(`/sessions/${encodeURIComponent(sessionId)}`, studentId), {
    method: "DELETE",
  });
}

export function sendSessionMessage(sessionId: string, question: string, allowOutsideKnowledge = false, studentId = "student_default") {
  return post<SessionAnswer>(`/sessions/${encodeURIComponent(sessionId)}/chat`, {
    question,
    allow_outside_knowledge: allowOutsideKnowledge,
    student_id: studentId,
  });
}

export function fetchCompletedQuizzes(studentId = "student_default") {
  return request<CompletedQuiz[]>(forStudent("/completed-quizzes", studentId));
}

export function fetchKnowledgeGraph() {
  return request<{ nodes: GraphNode[] }>("/graph");
}

export async function fetchUploadedMaterials() {
  const { materials } = await request<{ materials: UploadedMaterial[] }>("/ingest/materials");
  return materials;
}

export function uploadCourseFiles(files: File[]) {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return request<{
    units_created: number;
    sample_units: ContentUnit[];
    original_filenames?: string[];
    presentation_concepts_created?: number;
  }>(
    "/ingest/upload", { method: "POST", body },
  );
}

export function fetchStudentMastery(studentId: string) {
  return request<{ board: { concept_id: string; mastery: number }[] }>(
    `/mastery/${encodeURIComponent(studentId)}`,
  );
}

export function fetchAdaptiveQuiz(studentId: string, size: number, difficulty?: number, conceptId?: string) {
  return post<{ questions: QuizQuestion[] }>("/quiz", {
    student_id: studentId,
    size,
    difficulty,
    concept_id: conceptId,
  });
}

export function submitStudentAnswer(studentId: string, questionId: string, answer: string, attemptId?: string) {
  return post<{
    correct: boolean;
    correct_answer: string;
    explanation: string;
    concept_id: string;
    new_mastery: number;
    next_concept: string;
    next_difficulty: number;
  }>("/answer", { student_id: studentId, q_id: questionId, answer, attempt_id: attemptId });
}

export function triggerDiagnostic(studentId: string) {
  return post<{ masteries: Record<string, number>; questions?: QuizQuestion[] }>(
    forStudent("/diagnostic", studentId), {},
  );
}

export function fetchAblationBenchmarks() {
  return request<AblationResult>("/eval/ablation");
}

export function fetchRagasMetrics() {
  return request<RagasMetrics>("/eval/ragas");
}

export function formatMetric(value: number | undefined): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "Unavailable";
}
