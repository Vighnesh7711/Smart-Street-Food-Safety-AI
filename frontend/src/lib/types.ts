/**
 * Shared API types, mirroring the FastAPI schemas in
 * backend/app/schemas/. Kept hand-written rather than generated so the
 * frontend does not depend on a running backend to typecheck.
 */

export type UserRole = "vendor" | "consumer" | "reviewer" | "admin";

/** Mirrors backend app/models/enums.py::ScanStatus. These exact strings are
 * persisted and used as translation keys, so they must not drift. */
export const SCAN_STATUSES = [
  "Suitable",
  "Potential concern",
  "Application mismatch",
  "Insufficient information",
  "Needs review",
] as const;

export type ScanStatus = (typeof SCAN_STATUSES)[number];

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी (Hindi)" },
  { code: "mr", label: "मराठी (Marathi)" },
] as const;

export interface Token {
  access_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string | null;
  role: UserRole;
  /** null for consumers, and for vendors who have not onboarded a stall yet */
  vendor_id: number | null;
  preferred_language: string | null;
}

export interface Stall {
  id: number;
  vendor_id: number;
  name: string;
  food_category: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  /** The stall's active public code, derived server-side from qr_codes.
   * Null only if every code was revoked, which normal operation never does. */
  qr_code_id: string | null;
  hygiene_score: number | null;
  /** Derived server-side from the flags table. Replaces Phase 1's
   * `is_flagged`, which nothing ever wrote. */
  has_open_flag: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface StallQr {
  stall_id: number;
  /** The code in the public URL and inside the QR image. */
  code: string;
  /** Absolute frontend URL the QR encodes. */
  public_url: string;
  /** Root-relative path to the PNG on the API. */
  image_url: string;
}

// ---------------------------------------------------------------------------
// Public (unauthenticated) stall profile
// ---------------------------------------------------------------------------

export interface PublicHygieneSummary {
  score: number;
  band: ScoreBand;
  /** Null only for rows written before the column existed. */
  assessed_at: string | null;
}

export interface PublicScanSummary {
  /** Verdict only — the public payload deliberately omits the product name. */
  status: ScanStatus;
  scanned_at: string | null;
}

/**
 * Exactly what the public page receives.
 *
 * If this type ever gains a field, check the backend's schemas/public.py:
 * that is a deliberate allow-list, and the two must stay in step.
 */
export interface PublicStallProfile {
  stall_name: string;
  food_category: string | null;
  hygiene: PublicHygieneSummary | null;
  last_scan: PublicScanSummary | null;
  advisory_only: boolean;
  disclaimer: string;
}

export interface PublicStallLocation {
  stall_name: string;
  latitude: number;
  longitude: number;
  code: string;
  score: number | null;
  band: ScoreBand | null;
}

// ---------------------------------------------------------------------------
// Reviewer dashboard
// ---------------------------------------------------------------------------

/** `none` means never assessed — deliberately distinct from `bad`. */
export type ReviewBand = ScoreBand | "none";

export type ReviewSort =
  | "stall_name"
  | "hygiene"
  | "last_scan"
  | "last_activity"
  | "created_at";

export interface VendorRow {
  stall_id: number;
  stall_name: string;
  food_category: string | null;
  vendor_id: number;
  vendor_name: string | null;
  latest_score: number | null;
  latest_score_at: string | null;
  /** null when the stall has never been assessed. NOT the same as "bad". */
  band: ScoreBand | null;
  latest_scan_status: ScanStatus | null;
  latest_scan_at: string | null;
  last_activity_at: string | null;
  has_open_flag: boolean;
  open_flag_count: number;
}

export interface VendorListResponse {
  items: VendorRow[];
  total: number;
  skip: number;
  limit: number;
}

export interface ReviewerSummary {
  total_stalls: number;
  assessed_stalls: number;
  flagged_stalls: number;
  average_score: number | null;
  checks_last_7_days: number;
  bands: Record<ReviewBand, number>;
}

export interface HygieneHistoryPoint {
  check_id: number;
  score: number;
  visual_score: number;
  checklist_score: number | null;
  band: ScoreBand;
  formula_version: string;
  assessed_at: string | null;
}

export interface ScanHistoryRow {
  scan_id: number;
  status: ScanStatus;
  language_code: string;
  translation_failed: boolean;
  confidence_score: number | null;
  ocr_confidence: number | null;
  ingredient_count: number;
  scanned_at: string | null;
}

export interface DetectedIndicator {
  code: string;
  display_name: string;
  view: string;
  confidence: number;
  penalty: number;
  raw_labels: string[];
  /** [x1, y1, x2, y2] in the coordinate space described by `box_space`. */
  bbox: number[] | null;
}

export interface StallImageDetail {
  id: number;
  check_id: number;
  view_category: ViewCategory;
  view_display_name: string;
  image_url: string;
  detected_at: string | null;
  detections: DetectedIndicator[];
  /** Pixel dimensions the bounding boxes are expressed in. The overlay
   * divides by these, so it works at any display size. */
  box_space: { width: number; height: number } | null;
  quality_issues: string[];
}

export interface VendorDetail {
  stall_id: number;
  stall_name: string;
  food_category: string | null;
  vendor_id: number;
  vendor_name: string | null;
  address: string | null;
  created_at: string | null;
  current_score: number | null;
  current_band: ScoreBand | null;
  /** Null when there is no previous assessment — not 0. */
  score_delta: number | null;
  hygiene_history: HygieneHistoryPoint[];
  scan_history: ScanHistoryRow[];
  images: StallImageDetail[];
  open_flags: FlagRecord[];
}

export type FlagStatus = "open" | "resolved";

export interface FlagRecord {
  id: number;
  stall_id: number;
  stall_name: string | null;
  reason: string;
  status: FlagStatus;
  created_by_name: string | null;
  created_at: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
}

export interface FlagListResponse {
  items: FlagRecord[];
  total: number;
  skip: number;
  limit: number;
}

export interface StallCreate {
  name: string;
  food_category?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface Vendor {
  id: number;
  user_id: number;
  phone_number: string | null;
  preferred_language: string;
  created_at: string | null;
  full_name: string | null;
  email: string | null;
}

export interface VendorOnboardRequest {
  phone_number?: string | null;
  preferred_language: string;
  stall: StallCreate;
  food_items?: string[];
}

export interface VendorOnboardResponse {
  vendor: Vendor;
  stall: Stall;
  /** false when an existing vendor+stall pair was updated instead of created */
  created: boolean;
}

export interface MatchedIngredient {
  ingredient_id: number;
  canonical_name: string;
  category: string;
  risk_level: string;
  matched_text: string | null;
  matched_alias: string | null;
  match_confidence: number;
  match_method: string;
  parsed_percent: number | null;
}

export interface ImageQualityReport {
  ok: boolean;
  issues: string[];
  metrics: Record<string, number>;
  /** Human-readable guidance, e.g. "Image is too blurry — hold steady." */
  guidance: string | null;
}

export interface ScanResult {
  id: number;
  stall_id: number;
  product_name: string | null;
  status: ScanStatus;
  /** Canonical English. Always present, even when translation succeeded. */
  explanation: string;
  /** Vendor-language rendering; equals `explanation` when translation fell back. */
  explanation_translated: string;
  language_code: string;
  /** True when the translation provider failed and English is being shown. */
  translation_failed: boolean;
  recommendations: string[];
  matched_ingredients: MatchedIngredient[];
  ocr_confidence: number;
  match_confidence: number;
  rule_strength: number;
  confidence_score: number;
  /** True only for "Needs review" — retaking the photo can change the outcome. */
  retake_required: boolean;
  image_quality: ImageQualityReport | null;
  ingredient_text: string | null;
  scan_image_url: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Hygiene
// ---------------------------------------------------------------------------

/** Mirrors backend app/models/enums.py::ViewCategory. */
export const VIEW_CATEGORIES = [
  "overall",
  "prep_area",
  "storage_area",
  "waste_area",
] as const;

export type ViewCategory = (typeof VIEW_CATEGORIES)[number];

export type CheckStatus = "draft" | "awaiting_views" | "scored" | "failed";

export type ScoreBand = "good" | "fair" | "poor" | "bad";

export interface RequiredView {
  value: ViewCategory;
  display_name: string;
  /** Vendor-facing instruction, e.g. "Now photograph the storage area". */
  prompt: string;
  hint: string;
  /** 1-based position in the guided flow. */
  step: number;
}

export interface ChecklistItem {
  code: string;
  label: string;
  help_text: string;
}

export interface HygieneConfig {
  required_views: RequiredView[];
  checklist_items: ChecklistItem[];
  disclaimer: string;
}

export interface Coverage {
  ok: boolean;
  present: ViewCategory[];
  missing: ViewCategory[];
  /** Names the specific views still needed. Empty once complete. */
  message: string;
  next_view: ViewCategory | null;
  /** 0..1, for the progress bar. */
  progress: number;
}

export interface HygieneImage {
  id: number;
  view_category: ViewCategory;
  view_display_name: string;
  image_url: string;
  quality_ok: boolean;
  quality_issues: string[];
  created_at: string | null;
}

export interface IndicatorFinding {
  code: string;
  display_name: string;
  view: ViewCategory;
  severity: string;
  penalty: number;
  confidence: number;
  detection_count: number;
  raw_labels: string[];
}

export interface HygieneScore {
  visual_score: number;
  checklist_score: number | null;
  final_score: number;
  band: ScoreBand;
  formula_version: string;
  weights: Record<string, number>;
  computed_at: string | null;
}

export interface ChecklistAnswerRow extends ChecklistItem {
  answered: boolean;
  answer: boolean | null;
  satisfied: boolean;
}

export interface HygieneCheck {
  id: number;
  stall_id: number;
  status: CheckStatus;
  coverage: Coverage;
  images: HygieneImage[];
  score: HygieneScore | null;
  indicators_found: IndicatorFinding[];
  checklist: ChecklistAnswerRow[];
  created_at: string | null;
  scored_at: string | null;
  /** Always true. Stated in the payload so it cannot be presented as a
   * certification by a consumer that ignores the UI copy. */
  advisory_only: boolean;
  disclaimer: string;
}

export interface HygieneCheckSummary {
  id: number;
  stall_id: number;
  status: CheckStatus;
  final_score: number | null;
  band: ScoreBand | null;
  indicator_count: number;
  coverage_ok: boolean;
  missing_views: ViewCategory[];
  thumbnail_url: string | null;
  created_at: string | null;
  scored_at: string | null;
}
