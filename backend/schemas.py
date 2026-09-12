from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


# ==============================
# Auth & User Schemas
# ==============================

class OTPSendRequest(BaseModel):
    phone: str = Field(..., description="台灣手機號碼 (如 0912345678)")

    @field_validator("phone")
    @classmethod
    def validate_taiwan_phone(cls, v: str) -> str:
        v = v.strip().replace("-", "").replace(" ", "")
        if not re.match(r"^09\d{8}$", v):
            raise ValueError("請輸入有效的手機號碼 (09開頭共10碼)")
        return v


class OTPSendResponse(BaseModel):
    success: bool
    message: str
    expires_in: int = 180
    mock_otp: Optional[str] = Field(None, description="僅在開發/測試環境回傳以便驗證")


class OTPVerifyRequest(BaseModel):
    phone: str = Field(..., description="台灣手機號碼")
    otp: str = Field(..., min_length=6, max_length=6, description="6位數驗證碼")

    @field_validator("phone")
    @classmethod
    def validate_taiwan_phone(cls, v: str) -> str:
        v = v.strip().replace("-", "").replace(" ", "")
        if not re.match(r"^09\d{8}$", v):
            raise ValueError("請輸入有效的手機號碼 (09開頭共10碼)")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    community_id: Optional[int] = None
    verification_status: str
    credit_score: int
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)


# ==============================
# Community & Invitation Schemas
# ==============================

class CommunityCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="社區或大樓名稱")
    address: str = Field(..., min_length=5, max_length=255, description="社區地址")


class CommunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    created_at: datetime
    member_count: Optional[int] = 0



class InvitationCreateResponse(BaseModel):
    invitation_token: str
    share_url: str
    expires_at: datetime


class JoinCommunityRequest(BaseModel):
    token: str = Field(..., description="社區邀請 Token")


class JoinCommunityResponse(BaseModel):
    success: bool
    community_id: int
    community_name: str
    status: str
    message: str


# ==============================
# Item & Tool Schemas (SPEC_02)
# ==============================

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="工具名稱與型號")
    category: str = Field(..., description="分類 (POWER_TOOLS, CLEANING, CAMPING, GARDENING, HAND_TOOLS)")
    daily_rate: int = Field(..., gt=0, description="每日租金 (TWD)")
    market_value: int = Field(..., ge=100, le=100000, description="原價/市價 (TWD, 介於 100 至 100,000)")
    damage_tool_id: Optional[str] = Field(None, description="示範商品代碼 (TOOL_DRILL_01 等)")
    accessories: Optional[List[str]] = Field(default_factory=list, description="隨附配件清單")
    safety_notes: Optional[str] = Field(None, description="安全注意事項或使用限制")
    image_url: Optional[str] = Field(None, description="工具外觀照片網址")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid_cats = ["POWER_TOOLS", "CLEANING", "CAMPING", "GARDENING", "HAND_TOOLS"]
        v_upper = v.upper()
        if v_upper not in valid_cats:
            raise ValueError(f"無效的工具分類，必須為: {', '.join(valid_cats)}")
        return v_upper


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    category: Optional[str] = None
    daily_rate: Optional[int] = Field(None, gt=0)
    market_value: Optional[int] = Field(None, ge=100, le=100000)
    damage_tool_id: Optional[str] = None
    accessories: Optional[List[str]] = None
    safety_notes: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid_cats = ["POWER_TOOLS", "CLEANING", "CAMPING", "GARDENING", "HAND_TOOLS"]
        v_upper = v.upper()
        if v_upper not in valid_cats:
            raise ValueError(f"無效的工具分類，必須為: {', '.join(valid_cats)}")
        return v_upper


class ItemStatusUpdate(BaseModel):
    status: str = Field(..., description="工具狀態: AVAILABLE, RENTED, MAINTENANCE, DECOMMISSIONED")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ["AVAILABLE", "RENTED", "MAINTENANCE", "DECOMMISSIONED"]
        v_upper = v.upper()
        if v_upper not in valid_statuses:
            raise ValueError(f"無效的工具狀態，必須為: {', '.join(valid_statuses)}")
        return v_upper


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    owner_name: Optional[str] = None
    community_id: int
    name: str
    category: str
    daily_rate: int
    market_value: int
    damage_tool_id: Optional[str] = None
    status: str
    accessories: List[str] = Field(default_factory=list)
    safety_notes: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime


class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    inferred_tags: Optional[List[str]] = Field(default_factory=list)


# ==============================
# RAG & Local Knowledge Schemas
# ==============================

class RAGFAQRequest(BaseModel):
    question: str = Field(..., min_length=2, description="想詢問的操作問題")
    tool_name: Optional[str] = Field(None, description="工具名稱或品名關鍵字")
    tool_id: Optional[str] = Field(None, description="示範工具代碼 (如 TOOL_DRILL_01)")


class FAQMatch(BaseModel):
    question: str
    answer: str
    tool_id: str
    score: float


class RAGFAQResponse(BaseModel):
    answer: str
    source: str
    confidence: float
    matched_tool_id: Optional[str] = None
    related_qas: List[FAQMatch] = Field(default_factory=list)


class SafetyAlertResponse(BaseModel):
    category: str
    risk_level: str
    required_ppe: List[str]
    precautions: List[str]
    microcopy_tip: str


class EquipmentHealthResponse(BaseModel):
    item_id: int
    item_name: str
    health_grade: str
    total_rentals: int
    damage_count: int
    damage_rate: float
    summary: str
    maintenance_advice: str


class DamageCriteriaResponse(BaseModel):
    tool_id: str
    tool_name: str
    tool_category: str
    category: str = "損壞判定標準"
    minor_diff_criteria: str
    damage_detected_criteria: str
    excluded_scope: str
    source_ref: str
    last_verified_at: Optional[str] = None


class ToolContentChunkResponse(BaseModel):
    chunk_id: str
    tool_id: str
    tool_name: str
    tool_category: str
    category: str
    content: str
    source_ref: str
    use_case_tags: Optional[List[str]] = None
    last_verified_at: Optional[str] = None


class ScenarioToolMatch(BaseModel):
    tool_id: str
    tool_name: str
    tool_category: str
    matched_tags: List[str]
    content_summary: str
    source_ref: str



# ==============================
# Order & Compensation Schemas (SPEC_03)
# ==============================

class OrderCalculateRequest(BaseModel):
    item_id: int = Field(..., description="預約租借之工具 ID")
    start_date: date = Field(..., description="起租日期 (YYYY-MM-DD)")
    end_date: date = Field(..., description="歸還日期 (YYYY-MM-DD)")

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, values) -> date:
        return v


class OrderCalculateResponse(BaseModel):
    item_id: int
    item_name: str
    rent_days: int
    daily_rate: int
    total_rent: int
    base_deposit: int
    user_credit_score: int
    deposit_discount_rate: float
    actual_deposit: int
    authorized_total: int
    pool_coverage_applicable: bool
    breakdown_title: str = "總租金 + 履約押金 = 授權總額"
    cta_button_text: str = "發起預約並執行預授權鎖定 (歸還無誤即放行押金)"
    microcopy_tip: str = "預授權僅先鎖定信用額度，租期結束且工具確認無誤後，押金即刻解除鎖定釋出。"


class OrderCreateRequest(BaseModel):
    item_id: int = Field(..., description="預約租借之工具 ID")
    start_date: date = Field(..., description="起租日期 (YYYY-MM-DD)")
    end_date: date = Field(..., description="歸還日期 (YYYY-MM-DD)")


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    item_id: int
    item_name: Optional[str] = None
    renter_id: int
    renter_name: Optional[str] = None
    lender_id: int
    lender_name: Optional[str] = None
    start_date: date
    end_date: date
    rent_days: int
    daily_rate: int
    total_rent: int
    base_deposit: int
    actual_deposit: int
    status: str
    compensation_amount: int = 0
    pool_payout: int = 0
    created_at: datetime


class OrderCancelResponse(BaseModel):
    order_id: int
    status: str
    hours_before_start: float
    cancellation_fee: int
    refund_rent: int
    refund_deposit: int
    message: str


class CompensationCalculateRequest(BaseModel):
    order_id: int
    vision_result: str = Field(..., description="影像比對結果: MINOR_DIFF 或 DAMAGE_DETECTED")

    @field_validator("vision_result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        valid_results = ["MINOR_DIFF", "DAMAGE_DETECTED", "MATCH"]
        v_upper = v.upper()
        if v_upper not in valid_results:
            raise ValueError(f"無效的比對判定結果，必須為: {', '.join(valid_results)}")
        return v_upper


class CompensationCalculateResponse(BaseModel):
    order_id: int
    item_name: str
    market_value: int
    residual_value: int
    vision_result: str
    damage_ratio: float
    liability: int
    actual_deposit: int
    pool_eligible: bool
    pool_payout: int
    renter_out_of_pocket: int
    summary: str


class CompensationPoolStatusResponse(BaseModel):
    current_balance: int
    total_inflow: int
    total_outflow: int
    pool_name: str = "鄰里工具互助保障池"
    description: str = "由每筆順利結案訂單提撥 15% 累積，專用於示範工具非蓄意損壞之互助補貼支出。"


# ==============================
# Handover & Dispute Schemas (SPEC_04)
# ==============================

class HandoverCodeResponse(BaseModel):
    handover_code: str
    expires_in_seconds: int
    qr_payload: str


class HandoverVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="6位數取件核銷碼")


class HandoverVerifyResponse(BaseModel):
    success: bool
    status: str
    message: str


class CheckInRequest(BaseModel):
    image_url: Optional[str] = Field(None, description="存證照片 URL")
    image_base64: Optional[str] = Field(None, description="相機拍照 Base64 資料")
    notes: Optional[str] = Field(None, description="既有舊傷備註說明")


class CheckInResponse(BaseModel):
    order_id: int
    status: str
    checkin_image_url: str
    checksum_sha256: str
    is_same_object: bool = True
    verification_message: Optional[str] = None
    microcopy_guide: str = "請將工具置於引導框內，狸利會自動協助遮蔽住宅隱私。拍攝並標註初始舊傷，保護您的借用權益。"


class DisputeCreateRequest(BaseModel):
    order_id: int = Field(..., description="關聯之訂單 ID")
    reason: str = Field(..., min_length=5, description="申訴原因與異議說明")
    evidence_photos: Optional[List[str]] = Field(default_factory=list, description="佐證照片網址清單")


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    complainant_id: int
    complainant_name: Optional[str] = None
    reason: str
    status: str
    evidence_photos: List[str] = Field(default_factory=list)
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DisputeResolveRequest(BaseModel):
    status: str = Field(..., description="RESOLVED 或 REJECTED")
    resolution_notes: str = Field(..., min_length=2, description="處理覆核備註說明")


# ==============================
# AI Gateway & Vision Schemas (SPEC_02 & SPEC_04)
# ==============================

class A2RecommendRequest(BaseModel):
    prompt: str = Field(..., min_length=2, description="自然語言居家修繕或任務需求")


class A2RecommendResponse(BaseModel):
    tags: List[str]
    advice: str
    matched_item_ids: List[int] = Field(default_factory=list)


class ItemRecognizeResponse(BaseModel):
    suggested_name: str
    category: str
    damage_tool_id_match: Optional[str] = None
    suggested_accessories: List[str] = Field(default_factory=list)
    safety_warning: str


class CheckOutRequest(BaseModel):
    image_url: Optional[str] = Field(None, description="歸還存證照片 URL")
    image_base64: Optional[str] = Field(None, description="歸還存證照片 Base64")
    notes: Optional[str] = Field(None, description="歸還備註說明")


class CheckOutResponse(BaseModel):
    order_id: int
    status: str
    vision_evaluation: Dict[str, Any]
    deposit_refunded: int
    credit_score_earned: int
    message: str


class ToolConsistencyRequest(BaseModel):
    expected_name: Optional[str] = Field(None, description="使用者輸入或選擇之工具品名")
    expected_category: Optional[str] = Field(None, description="預期工具分類 (POWER_TOOLS, HAND_TOOLS 等)")
    image_url: Optional[str] = Field(None, description="欲驗證照片之 URL")
    image_base64: Optional[str] = Field(None, description="欲驗證照片之 Base64 編碼字串")


class ToolConsistencyResponse(BaseModel):
    is_consistent: bool = Field(..., description="文字品項與相片辨識是否一致")
    detected_tool: str = Field(..., description="AI 實際辨識出之工具品名")
    expected_tool: Optional[str] = Field(None, description="使用者預期之工具品名")
    confidence: float = Field(..., description="辨識信心度")
    requires_retake: bool = Field(..., description="是否需要重新拍照")
    mismatch_reason: Optional[str] = Field(None, description="不一致或重拍原因說明")
    token_cost_estimate: int = Field(default=258, description="邊緣壓縮後預估 Vision Token 消耗數")


class SameObjectVerifyResponse(BaseModel):
    is_same_object: bool = Field(..., description="Check-in 照與原始上架照是否為同一個物件")
    confidence: float = Field(..., description="比對信心度")
    difference_notes: str = Field(..., description="差異細節備註")
    requires_retake: bool = Field(..., description="是否需要重新對齊拍照")
    token_cost_estimate: int = Field(default=258, description="邊緣壓縮後預估 Vision Token 消耗數")
    recommended_angle: Optional[str] = Field(default="建議保持 45 度側面視角，露出品牌 LOGO 與機身銘牌，有助降低比對成本。", description="建議拍攝角度指引")
