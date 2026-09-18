from typing import Optional
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    ItemCreate,
    ItemUpdate,
    ItemStatusUpdate,
    ItemResponse,
    ItemListResponse,
    EquipmentHealthResponse,
    ItemRecognizeResponse,
    ToolConsistencyResponse,
    SameObjectVerifyRequest,
    SameObjectVerifyResponse,
)
from .auth import get_current_user, get_validated_user
from ..services import item_service
from ..services.rag_local_service import calculate_equipment_health
from ..ai.gateway import AIGateway

router = APIRouter(prefix="/api/v1/items", tags=["Items (工具管理)"])


@router.post(
    "/recognize",
    response_model=ItemRecognizeResponse,
    summary="D1 工具影像拍照辨識預填 (AI Gateway)",
)
async def recognize_tool(
    request: Request,
    filename_hint: Optional[str] = Query(None, description="上傳檔案名稱或型號線索"),
    current_user: User = Depends(get_validated_user),
):
    """
    D1 AI 拍照輔助辨識上架 (Gemini Vision 代理)。
    - 支援相片檔案實體上傳 (multipart/form-data) 或 filename_hint 線索。
    - 自動提取建議品名、工具大類別、可能隨附配件與操作安全警語。
    - 嚴格限制：禁止自動估算市價或建議租金！
    """
    image_bytes = None
    hint = filename_hint
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            uploaded_file = form.get("file")
            if uploaded_file and hasattr(uploaded_file, "read"):
                image_bytes = await uploaded_file.read()
                if not hint and hasattr(uploaded_file, "filename") and uploaded_file.filename:
                    hint = uploaded_file.filename
            if not hint and "filename_hint" in form:
                hint = str(form.get("filename_hint"))
        except Exception as e:
            print(f"[Warning] Failed to parse multipart form in recognize_tool: {e}")
    elif "application/json" in content_type:
        try:
            body = await request.json()
            if "image_base64" in body and body["image_base64"]:
                import base64
                b64_str = body["image_base64"]
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                image_bytes = base64.b64decode(b64_str)
            if not hint and "filename_hint" in body:
                hint = body.get("filename_hint")
        except Exception as e:
            print(f"[Warning] Failed to parse json in recognize_tool: {e}")

    gateway = AIGateway.get_instance()
    return gateway.recognize_tool(
        user_id=current_user.id,
        image_bytes=image_bytes,
        filename_hint=hint,
    )


@router.post(
    "/verify-consistency",
    response_model=ToolConsistencyResponse,
    summary="驗證相片與所選工具名稱之一致性 (Consistency Verification)",
)
async def verify_tool_consistency(
    request: Request,
    expected_name: Optional[str] = Query(None, description="預期品名 (如 BOSCH 震動電鑽)"),
    expected_category: Optional[str] = Query(None, description="預期分類 (如 POWER_TOOLS)"),
    current_user: User = Depends(get_current_user),
):
    """
    檢查相片辨識結果與文字品項是否吻合。
    若辨識不一致或模糊，明確回傳 requires_retake=True 要求重新拍照。
    """
    image_bytes = None
    hint = None
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            uploaded_file = form.get("file")
            if uploaded_file and hasattr(uploaded_file, "read"):
                image_bytes = await uploaded_file.read()
                if hasattr(uploaded_file, "filename"):
                    hint = uploaded_file.filename
            if "expected_name" in form:
                expected_name = str(form.get("expected_name"))
            if "expected_category" in form:
                expected_category = str(form.get("expected_category"))
        except Exception as e:
            print(f"[Warning] Failed to parse multipart form in verify_tool_consistency: {e}")
    elif "application/json" in content_type:
        try:
            body = await request.json()
            if not expected_name:
                expected_name = body.get("expected_name")
            if not expected_category:
                expected_category = body.get("expected_category")
            if "image_base64" in body and body["image_base64"]:
                import base64
                b64_str = body["image_base64"]
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                image_bytes = base64.b64decode(b64_str)
            hint = body.get("filename_hint")
        except Exception as e:
            print(f"[Warning] Failed to parse json in verify_tool_consistency: {e}")

    gateway = AIGateway.get_instance()
    return gateway.verify_tool_consistency(
        user_id=current_user.id,
        image_bytes=image_bytes,
        expected_name=expected_name,
        expected_category=expected_category,
        filename_hint=hint,
    )


@router.get("/ai-status", summary="查詢 AI Gateway 與 Gemini Vision 連線狀態")
def get_ai_status_endpoint():
    """
    查詢 Gemini Vision API 連線狀態、金鑰配置與當前啟用引擎。
    """
    gateway = AIGateway.get_instance()
    return gateway.client.get_ai_status()


@router.post(
    "/verify-same-object",
    response_model=SameObjectVerifyResponse,
    summary="驗證現場取件照與原始上架照是否為同一實體物件 (Same Object Verification)",
)
async def verify_same_object(
    request: Request,
    item_name: Optional[str] = Query(None, description="登記之工具品名"),
    original_image_url: Optional[str] = Query(None, description="出借人原始上架相片 URL"),
    current_user: User = Depends(get_current_user),
):
    """
    Check-in 取件現場照片 vs 原始上架照片 特徵核對。
    防止拿錯工具、品牌調包或上傳無關生活雜物。
    """
    import os
    import base64
    from pathlib import Path

    # 依據 robust-engineering 規範：頂層顯式初始化所有變數，物理性杜絕 UnboundLocalError
    image_bytes: Optional[bytes] = None
    original_bytes: Optional[bytes] = None
    hint: Optional[str] = None
    image_url: Optional[str] = None

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body_json = await request.json()
            req_obj = SameObjectVerifyRequest(**body_json)
            if not item_name and req_obj.item_name:
                item_name = req_obj.item_name
            if not original_image_url and req_obj.original_image_url:
                original_image_url = req_obj.original_image_url
            if req_obj.image_url:
                image_url = req_obj.image_url
            if req_obj.filename_hint:
                hint = req_obj.filename_hint
            if req_obj.image_base64:
                b64_str = req_obj.image_base64.split(",", 1)[1] if "," in req_obj.image_base64 else req_obj.image_base64
                image_bytes = base64.b64decode(b64_str)
            if req_obj.original_image_base64:
                b64_orig = req_obj.original_image_base64.split(",", 1)[1] if "," in req_obj.original_image_base64 else req_obj.original_image_base64
                original_bytes = base64.b64decode(b64_orig)
        except Exception as e:
            print(f"[Warning] Failed to parse json via SameObjectVerifyRequest: {e}")
    elif "multipart/form-data" in content_type:
        try:
            form = await request.form()
            uploaded_file = form.get("file")
            if uploaded_file and hasattr(uploaded_file, "read"):
                image_bytes = await uploaded_file.read()
                if hasattr(uploaded_file, "filename"):
                    hint = uploaded_file.filename
            if "item_name" in form:
                item_name = str(form.get("item_name"))
            if "original_image_url" in form:
                original_image_url = str(form.get("original_image_url"))
            if "image_url" in form:
                image_url = str(form.get("image_url"))
            if "filename_hint" in form:
                hint = str(form.get("filename_hint"))
        except Exception as e:
            print(f"[Warning] Failed to parse multipart form in verify_same_object: {e}")

    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent

    # 嘗試載入現場照片二進位 (支援 image_url、Base64 或檔名提示)
    if not image_bytes and image_url:
        if image_url.startswith("data:"):
            try:
                import base64
                b64_str = image_url.split(",", 1)[1] if "," in image_url else image_url
                image_bytes = base64.b64decode(b64_str)
            except Exception:
                pass
        else:
            fname = os.path.basename(image_url.split("?")[0])
            hint_candidates = [
                project_root / "frontend" / "public" / "test_assets" / fname,
                project_root / "frontend" / "dist" / "test_assets" / fname,
                project_root / "test_assets" / fname,
                project_root / "frontend" / "public" / fname,
                project_root / fname,
                Path(os.getcwd()) / "frontend" / "public" / "test_assets" / fname,
                Path(os.getcwd()) / fname,
            ]
            for hp in hint_candidates:
                if hp.exists():
                    try:
                        with open(hp, "rb") as f:
                            image_bytes = f.read()
                        break
                    except Exception:
                        pass

    if not image_bytes and hint:
        import re
        m = re.search(r"([\w\-]+\.(?:jpg|jpeg|png))", hint, re.IGNORECASE)
        if m:
            fname_hint = m.group(1)
            hint_candidates = [
                project_root / "frontend" / "public" / "test_assets" / fname_hint,
                project_root / "frontend" / "dist" / "test_assets" / fname_hint,
                project_root / "test_assets" / fname_hint,
                project_root / "frontend" / "public" / fname_hint,
                project_root / fname_hint,
                Path(os.getcwd()) / "frontend" / "public" / "test_assets" / fname_hint,
                Path(os.getcwd()) / fname_hint,
            ]
            for hp in hint_candidates:
                if hp.exists():
                    try:
                        with open(hp, "rb") as f:
                            image_bytes = f.read()
                        break
                    except Exception:
                        pass

    # 嘗試載入出借人原始相片二進位以供雙圖比對
    if not original_bytes and original_image_url:
        if original_image_url.startswith("data:"):
            try:
                import base64
                b64_orig = original_image_url.split(",", 1)[1] if "," in original_image_url else original_image_url
                original_bytes = base64.b64decode(b64_orig)
            except Exception:
                pass
        else:
            fname = os.path.basename(original_image_url.split("?")[0])
            candidate_paths = [
                project_root / "frontend" / "public" / "test_assets" / fname,
                project_root / "frontend" / "dist" / "test_assets" / fname,
                project_root / "test_assets" / fname,
                project_root / "frontend" / "public" / fname,
                project_root / fname,
                Path(os.getcwd()) / "frontend" / "public" / "test_assets" / fname,
                Path(os.getcwd()) / fname,
            ]
            for cp in candidate_paths:
                if cp.exists():
                    try:
                        with open(cp, "rb") as f:
                            original_bytes = f.read()
                        break
                    except Exception:
                        pass

    gateway = AIGateway.get_instance()
    hint_text = hint or ""
    res = gateway.verify_same_object(
        user_id=current_user.id,
        original_image_bytes=original_bytes,
        checkin_image_bytes=image_bytes,
        item_name=item_name or "修繕工具",
        hint_text=hint_text,
    )
    return SameObjectVerifyResponse(
        is_same_object=res.get("is_same_object", False),
        confidence=float(res.get("confidence", 0.9)),
        difference_notes=res.get("difference_notes", "特徵吻合，確認為同一實體物件。"),
        requires_retake=res.get("requires_retake", False),
        token_cost_estimate=res.get("token_cost_estimate", 258),
        recommended_angle=res.get("recommended_angle", "建議保持 45 度側面視角，露出品牌 LOGO 與機身銘牌。"),
    )


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED, summary="上架新工具")
def create_item(
    item_in: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_validated_user),
):
    """
    住戶正式上架閒置工具。
    - 需為該社區已驗證住戶 (VALIDATED)。
    - market_value 原價必須介於 100 至 100,000 元之間。
    - 自動綁定當前登入者與所屬社區。
    """
    item = item_service.create_item(db, current_user, item_in)
    return item_service.to_item_response(item)


@router.get("/", response_model=ItemListResponse, summary="取得社區工具清單與檢索")
def list_items(
    query: Optional[str] = Query(None, description="關鍵字搜尋 (品名或注意事項)"),
    category: Optional[str] = Query(None, description="工具類別篩選"),
    status: Optional[str] = Query(None, description="工具狀態篩選 (若未指定或為 ALL 則回傳全量狀態，包括 AVAILABLE 與 RENTED)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    取得使用者所屬社區的工具清單。
    - 嚴格落實社區資料隔離：僅可查看自己所屬 community_id 下的工具。
    """
    if not current_user.community_id:
        return ItemListResponse(items=[], total=0, inferred_tags=[])

    items, tags = item_service.list_items(
        db,
        community_id=current_user.community_id,
        category=category,
        status_filter=status,
        query=query,
    )
    return ItemListResponse(
        items=[item_service.to_item_response(i) for i in items],
        total=len(items),
        inferred_tags=tags,
    )


@router.get("/{item_id}", response_model=ItemResponse, summary="取得工具詳細資訊")
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查看特定工具詳情。
    - 跨社區隔離檢核：若非同社區住戶則回傳 403。
    """
    item = item_service.get_item(db, item_id, current_user=current_user)
    return item_service.to_item_response(item)


@router.patch("/{item_id}/status", response_model=ItemResponse, summary="變更工具狀態 (上下架/保養)")
def update_item_status(
    item_id: int,
    status_in: ItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    工具擁有者更新工具狀態 (AVAILABLE, RENTED, MAINTENANCE, DECOMMISSIONED)。
    """
    item = item_service.update_item_status(db, item_id, status_in.status, current_user)
    return item_service.to_item_response(item)


@router.put("/{item_id}", response_model=ItemResponse, summary="修改工具資訊")
def update_item(
    item_id: int,
    item_in: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    工具擁有者修改工具名稱、租金、原價等資訊。
    """
    item = item_service.update_item(db, item_id, item_in, current_user)
    return item_service.to_item_response(item)


@router.get("/{item_id}/health", response_model=EquipmentHealthResponse, summary="UC-5 工具裝備健康評級與摘要")
def get_item_health(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    依歷史租借次數與損壞回報，以規則引擎計算工具健康等級 (A/B/C) 與保養建議。
    - 零外部 LLM 依賴，延遲 < 50ms。
    """
    # Verify access permission first
    item_service.get_item(db, item_id, current_user=current_user)
    return calculate_equipment_health(db, item_id)
