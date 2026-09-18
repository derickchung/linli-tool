/**
 * LinLi Tool (鄰里工具) - Frontend Type Definitions
 * Strict alignment with Backend Models & Schemas
 */

export type VerificationStatus = 'PENDING' | 'VALIDATED' | 'REJECTED';

export type OrderStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'PICKED_UP'
  | 'IN_USE'
  | 'INSPECTION'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'DISPUTED'
  | 'REJECTED_RETAKE';

export type DisputeStatus = 'OPEN' | 'UNDER_REVIEW' | 'RESOLVED' | 'REJECTED';

export type VisionResult = 'MATCH' | 'MINOR_DIFF' | 'DAMAGE_DETECTED' | 'INVALID_OBJECT' | 'TOOL_SWAP_DETECTED';

export interface VisionEvaluation {
  result: VisionResult;
  confidence: number;
  difference_notes: string;
  recommended_angle?: string;
  requires_retake?: boolean;
  ai_model?: string;
  duration_ms?: number;
  token_cost_estimate?: number;
}

export interface UserProfile {
  id: number;
  phone: string;
  name: string;
  community_id?: number | null;
  community_name?: string | null;
  verification_status: VerificationStatus;
  credit_score: number;
  created_at?: string;
}

export interface Community {
  id: number;
  name: string;
  address: string;
  member_count?: number;
  created_at?: string;
}

export interface InvitationResponse {
  invitation_token: string;
  share_url: string;
  expires_at: string;
}

export interface JoinCommunityResponse {
  success: boolean;
  community_id: number;
  community_name: string;
  status: VerificationStatus;
  message: string;
}

export interface Item {
  id: number;
  owner_id: number;
  community_id: number;
  name: string;
  category: string;
  daily_rate: number;
  market_value: number;
  damage_tool_id?: string;
  status: string;
  accessories?: string[];
  safety_tips?: string[];
  safety_notes?: string;
  image_url?: string;
  created_at?: string;
  brand?: string;
  short_name?: string;
  walk_time?: string;
  display_tags?: string[];
}

export interface ItemListResponse {
  items: Item[];
  total: number;
  inferred_tags: string[];
}

export interface OrderCalculateRequest {
  item_id: number;
  start_date: string; // YYYY-MM-DD
  end_date: string;   // YYYY-MM-DD
}

export interface OrderCalculateResponse {
  item_id: number;
  item_name: string;
  rent_days: number;
  daily_rate: number;
  total_rent: number;
  base_deposit: number;
  user_credit_score: number;
  deposit_discount_rate: number;
  actual_deposit: number;
  authorized_total: number;
  pool_coverage_applicable: boolean;
}

export interface OrderCreateRequest {
  item_id: number;
  start_date?: string;
  end_date?: string;
  rent_days?: number;
  payment_method?: string;
  notes?: string;
}

export interface OrderResponse {
  id: number;
  order_no: string;
  item_id: number;
  item_name?: string;
  renter_id: number;
  renter_name?: string;
  lender_id: number;
  lender_name?: string;
  start_date?: string;
  end_date?: string;
  rent_days?: number;
  daily_rate?: number;
  total_rent: number;
  base_deposit: number;
  actual_deposit: number;
  status: OrderStatus;
  compensation_amount?: number;
  pool_payout?: number;
  created_at?: string;
  checkin_image_url?: string;
  checkin_sha256?: string;
  item?: any;
  renter?: any;
}

export interface HandoverCodeResponse {
  handover_code: string;
  expires_in_seconds: number;
  qr_payload: string;
}

export interface HandoverVerifyResponse {
  success: boolean;
  status: OrderStatus;
  message: string;
}

export interface CheckInResponse {
  order_id: number;
  status: OrderStatus;
  checkin_image_url?: string;
  checksum_sha256: string;
  is_same_object?: boolean;
  verification_message?: string;
}


export interface CheckOutResponse {
  order_id: number;
  status: OrderStatus;
  vision_evaluation: VisionEvaluation;
  deposit_refunded: number;
  credit_score_earned: number;
  message: string;
}

export interface DisputeCreateRequest {
  order_id: number;
  reason: string;
  evidence_images?: string[];
}

export interface DisputeResponse {
  id: number;
  order_id: number;
  complainant_id: number;
  complainant_name?: string;
  reason: string;
  status: DisputeStatus;
  evidence_photos?: string[];
  resolution_notes?: string;
  created_at: string;
  resolved_at?: string;
}

export interface ItemRecognizeResponse {
  suggested_name: string;
  category: string;
  damage_tool_id_match?: string;
  suggested_accessories: string[];
  safety_warning: string;
  is_recognized?: boolean;
  unrecognized_reason?: string;
}

// Aliases for compatibility with Vision AI service
export type ToolRecognitionResponse = ItemRecognizeResponse;

export interface A2RecommendResponse {
  tags: string[];
  advice: string;
  matched_item_ids: number[];
}

export type ScenarioRecommendResponse = A2RecommendResponse;

export interface ToolConsistencyResponse {
  is_consistent: boolean;
  detected_tool: string;
  expected_tool?: string;
  confidence: number;
  requires_retake: boolean;
  mismatch_reason?: string | null;
  token_cost_estimate: number;
}

export interface SameObjectVerifyResponse {
  is_same_object: boolean;
  confidence: number;
  difference_notes: string;
  requires_retake: boolean;
  token_cost_estimate: number;
  recommended_angle?: string;
}

