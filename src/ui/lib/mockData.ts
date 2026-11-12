import type { AblationPoint, Citation, ContentUnit, GraphNode, QuizQuestion, RagasMetrics } from "./api";

export interface ConceptNode {
  concept_id: string;
  name: string;
  topic: string;
  prerequisites: string[];
  evidence_units: string[];
  evidenceCount: number;
  evidence_details?: GraphNode["evidence_details"];
  mastery: number;
  status: "mastered" | "learning" | "weak" | "unvisited";
  description: string;
  keyTakeaways: string[];
}

export interface Question extends Omit<QuizQuestion, "options"> {
  options: string[];
  answer: string;
  explanation: string;
  sympy_verified: boolean;
}

export interface AttachedFile {
  id: string;
  name: string;
  type: "pdf" | "video" | "image" | "file";
  extension?: string;
  size?: string;
  previewUrl?: string;
  previewHeading?: string;
  previewLines?: string[];
}

export interface ChatMessage {
  id: string;
  sender: "student" | "tutor";
  text: string;
  timestamp: string;
  citations?: Omit<Citation, "open_url">[];
  attachment?: AttachedFile;
  attachments?: AttachedFile[];
  isRefusal?: boolean;
  hindiTranslation?: string;
}

export const MOCK_CONTENT_UNITS: ContentUnit[] = [
  {
    unit_id: "ppt_INT255_Unit_5_s4",
    source_id: "INT255 Unit 5 (demo)",
    source_type: "slides",
    location: { slide: 4 },
    text: "A probability assigns each event a value between 0 and 1, inclusive.",
  },
  {
    unit_id: "ppt_INT255_Unit_5_s15",
    source_id: "INT255 Unit 5 (demo)",
    source_type: "slides",
    location: { slide: 15 },
    text: "Bayes' theorem updates the prior probability of an event after observing evidence.",
  },
];

export const MOCK_CONCEPTS: ConceptNode[] = [
  {
    concept_id: "c-prob-basics",
    name: "Probability and distributions",
    topic: "Probability & Foundations",
    prerequisites: [],
    evidence_units: [MOCK_CONTENT_UNITS[0].unit_id],
    evidenceCount: 1,
    mastery: 0.3,
    status: "weak",
    description: "Represent uncertainty with probabilities and distributions.",
    keyTakeaways: ["Probabilities lie between 0 and 1."],
  },
  {
    concept_id: "c-bayes-theorem",
    name: "Bayes’ theorem",
    topic: "Probability & Foundations",
    prerequisites: ["c-prob-basics"],
    evidence_units: [MOCK_CONTENT_UNITS[1].unit_id],
    evidenceCount: 1,
    mastery: 0.3,
    status: "unvisited",
    description: "Update a probability after observing new evidence.",
    keyTakeaways: ["The posterior is conditional on the observed evidence."],
  },
];

export const MOCK_QUESTIONS: Question[] = [
  {
    q_id: "q_prob_1",
    concept_id: "c-prob-basics",
    topic: "Probability & Foundations",
    source_location: { slide: 4 },
    difficulty: 1,
    type: "mcq",
    stem: "What is the valid range for the probability of an event?",
    options: ["[-1, 1]", "[0, 1]", "(0, infinity)", "[-infinity, infinity]"],
    answer: "[0, 1]",
    explanation: MOCK_CONTENT_UNITS[0].text,
    verified: true,
    verifier_agreement: 1,
    sympy_verified: false,
  },
  {
    q_id: "q_bayes_1",
    concept_id: "c-bayes-theorem",
    topic: "Probability & Foundations",
    source_location: { slide: 15 },
    difficulty: 2,
    type: "mcq",
    stem: "In Bayes' theorem, what does P(A|B) represent?",
    options: [
      "Prior probability of A before evidence B is observed",
      "Posterior probability of A given that evidence B has occurred",
      "Joint probability that both A and B occur simultaneously",
      "Marginal probability of evidence B",
    ],
    answer: "Posterior probability of A given that evidence B has occurred",
    explanation: MOCK_CONTENT_UNITS[1].text,
    verified: true,
    verifier_agreement: 1,
    sympy_verified: false,
  },
];

interface BenchmarkData {
  ragas_metrics: RagasMetrics;
  learning_curves: AblationPoint[];
  ablation_summary: {
    sessions_compared: number;
    random_baseline_final: string;
    adaptive_bkt_final: string;
    net_mastery_gain: string;
    p_value: string;
    sample_size: string;
  };
}

// Recorded demo simulation from AblationSimulator with its default settings.
export const EVALUATION_ABLATION_DATA: BenchmarkData = {
  ragas_metrics: {},
  learning_curves: [
    { session: "Session 1", random: 31.7, adaptive: 33.2 },
    { session: "Session 2", random: 32.8, adaptive: 35.6 },
    { session: "Session 3", random: 34.0, adaptive: 38.0 },
    { session: "Session 4", random: 35.2, adaptive: 40.3 },
    { session: "Session 5", random: 36.3, adaptive: 42.6 },
  ],
  ablation_summary: {
    sessions_compared: 5,
    random_baseline_final: "36.3%",
    adaptive_bkt_final: "42.6%",
    net_mastery_gain: "+6.3%",
    p_value: "unreported",
    sample_size: "30 simulated students across 8 course concepts",
  },
};
