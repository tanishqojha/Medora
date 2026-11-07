export type Meta = {
  hospital: string;
  synthetic: boolean;
  replay: boolean;
  user: { name: string; role: Role };
  counts: { stuck: number; review: number; nurse: number; merges: number; jobs: number };
};
export type Role = "coordinator" | "clinical_lead" | "nurse" | "admin" | "data_steward";
export type SourceRef = {
  kind: string;
  file?: string;
  filename?: string;
  row?: number;
  cells?: Record<string, string>;
  crops?: Record<string, { crop?: string; page?: number; line?: number }>;
  reviewed_by?: string;
};
export type RankInputs = {
  days_overdue: number;
  missed_count: number;
  attempts: number;
  unreachable: boolean;
  due_by: string;
  patient_id: string;
};
export type StuckItem = {
  id: string;
  kind: "overdue" | "missed" | "unreachable";
  reason_line: string;
  rank_inputs: RankInputs;
  rank: number;
  patient_id: string;
  display_name: string;
  sex: string | null;
  birth_year: number | null;
  synthetic: boolean;
  pathway_key: string;
  pathway_name: string;
  pathway_version: number;
  from_step: string;
  expected_step: string;
  due_by: string;
  obligation_id: string;
  rule_version: string;
  from_source: SourceRef | null;
  last_attempt: string | null;
};
export type EventRow = {
  id: string;
  type: string;
  occurred_at: string;
  effective_at: string;
  source_ref: SourceRef;
  confidence: number;
  payload: Record<string, string>;
  actor: string;
};

/** Doctor panel: one dated schedule fact. Never a cause, reason or result (api/medora/history.py). */
export type HistoryPointData = {
  id: string;
  type: string;
  label: string;
  detail: string | null;
  date: string;
  days_since_previous: number | null;
  source_ref: SourceRef | null;
  confidence: number | null;
  synthetic: boolean;
};
export type DoctorPatient = {
  id: string;
  display_name: string;
  sex: string | null;
  birth_year: number | null;
  points: number;
  last_at: string;
  synthetic: boolean;
};
export type DoctorHistory = {
  patient: { id: string; display_name: string; sex: string | null; birth_year: number | null; synthetic: boolean };
  points: HistoryPointData[];
  note: string;
};
