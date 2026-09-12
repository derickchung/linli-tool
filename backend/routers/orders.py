from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    OrderCalculateRequest,
    OrderCalculateResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderCancelResponse,
    CompensationCalculateRequest,
    CompensationCalculateResponse,
    CompensationPoolStatusResponse,
    HandoverCodeResponse,
    HandoverVerifyRequest,
    HandoverVerifyResponse,
    CheckInRequest,
    CheckInResponse,
    CheckOutRequest,
    CheckOutResponse,
)
from .auth import get_current_user, get_validated_user
from ..services import order_service, compensation_service, handover_service
from ..ai.gateway import AIGateway

router = APIRouter(prefix="/api/v1/orders", tags=["Orders (租借預約與押金計算)"])


@router.post(
    "/calculate",
    response_model=OrderCalculateResponse,
    summary="即時費用與信用分押金試算 (金流預授權卡片資料)",
)
def calculate_order(
    req: OrderCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    即時計算租借天數、總租金、信用分三級距押金與預授權總額。
    - 後端統一計費，前端僅做展示，防範金額竄改。
    """
    return order_service.calculate_order_fee(
        db,
        user=current_user,
        item_id=req.item_id,
        start_date=req.start_date,
        end_date=req.end_date,
    )


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立租借預約訂單",
)
def create_order(
    req: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_validated_user),
):
    """
    住戶發起預約工具。
    - 需為該社區已驗證住戶 (VALIDATED)。
    - 禁止租借自己上架之工具 (400)。
    - 並發排他排程鎖定：同檔期已預約即刻回傳 409 Conflict。
    - 成功建立後，初始狀態為 CONFIRMED。
    """
    order = order_service.create_order(
        db,
        user=current_user,
        item_id=req.item_id,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return order_service.to_order_response(order)


@router.get(
    "/",
    response_model=List[OrderResponse],
    summary="取得使用者租借/出借訂單列表",
)
def list_orders(
    role: Optional[str] = Query(None, description="篩選角色: renter (借入) 或 lender (借出)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = order_service.list_user_orders(db, current_user, role=role)
    return [order_service.to_order_response(o) for o in orders]


@router.get(
    "/pool/status",
    response_model=CompensationPoolStatusResponse,
    summary="查詢平台損壞互助保障池狀態與餘額",
)
def get_pool_status(db: Session = Depends(get_db)):
    """
    查詢社區平台互助保障池之即時餘額、累計提撥與累計支出。
    """
    current_balance, inflow, outflow = compensation_service.get_current_pool_balance(db)
    return CompensationPoolStatusResponse(
        current_balance=current_balance,
        total_inflow=inflow,
        total_outflow=outflow,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="取得單一訂單明細",
)
def get_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = order_service.get_order(db, current_user, order_id)
    return order_service.to_order_response(order)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderCancelResponse,
    summary="取消租借訂單 (24 小時退費違約金政策)",
)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    取消預約訂單。
    - 起租前 >= 24 小時：全額免費取消 (手續費 0)。
    - 起租前 < 24 小時：收取 20% 租金手續費補貼出借人，其餘退款。
    """
    return order_service.cancel_order(db, current_user, order_id)


@router.post(
    "/compensation/calculate",
    response_model=CompensationCalculateResponse,
    summary="損壞補貼與責任計算 (平台互助保障池機制)",
)
def calculate_order_compensation(
    req: CompensationCalculateRequest,
    db: Session = Depends(get_db),
):
    """
    依影像比對結果（MINOR_DIFF 30% / DAMAGE_DETECTED 100%）試算責任與互助保障池撥付額。
    - 示範工具享有互助保障池差額補貼（不透支餘額）。
    - 非示範工具回退純押金制。
    - 嚴格遵守微文案合規（全面落實互助保障專有名詞規範）。
    """
    return compensation_service.calculate_compensation(
        db,
        order_id=req.order_id,
        vision_result=req.vision_result,
    )


@router.get(
    "/{order_id}/handover/code",
    response_model=HandoverCodeResponse,
    summary="取得取件 60 秒動態 TOTP 核銷碼 (借用人端)",
)
def get_handover_code(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    借用人取得現場交接時出示之動態 6 碼核銷碼 (TOTP 60s)。
    """
    code, expires_in, qr_payload = handover_service.get_handover_code_for_user(
        db, current_user, order_id
    )
    return HandoverCodeResponse(
        handover_code=code,
        expires_in_seconds=expires_in,
        qr_payload=qr_payload,
    )


@router.post(
    "/{order_id}/handover/verify",
    response_model=HandoverVerifyResponse,
    summary="核銷取件碼並確認取件 (出借人端)",
)
def verify_handover(
    order_id: int,
    req: HandoverVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    出借人現場輸入借用人出示的 6 碼核銷碼。
    - 核銷成功後，訂單狀態變更為 PICKED_UP。
    """
    order = handover_service.verify_and_confirm_pickup(
        db, current_user, order_id, req.code
    )
    return HandoverVerifyResponse(
        success=True,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        message="取件核銷成功！工具已順利移交借用人。",
    )


@router.post(
    "/{order_id}/check-in",
    response_model=CheckInResponse,
    summary="Check-in 拍照存證與雜湊校驗 (Ghost Overlay)",
)
def checkin_order(
    order_id: int,
    req: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    借用人完成取件後，拍攝初始工具外觀存證照片。
    - 後端計算 SHA-256 Checksum 存證防竄改。
    - 訂單狀態推進至 IN_USE。
    """
    order, checksum, verify_res = handover_service.process_checkin(
        db,
        user=current_user,
        order_id=order_id,
        image_url=req.image_url,
        image_base64=req.image_base64,
        notes=req.notes,
    )
    return CheckInResponse(
        order_id=order.id,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        checkin_image_url=order.checkin_image_url,
        checksum_sha256=checksum,
        is_same_object=verify_res.get("is_same_object", True),
        verification_message=verify_res.get("difference_notes", "取件照片特徵核對吻合，確認為同一實體物件。"),
    )


@router.post(
    "/{order_id}/check-out",
    response_model=CheckOutResponse,
    summary="Check-out 歸還相片差分比對結案 (Ghost Overlay)",
)
def checkout_order(
    order_id: int,
    req: CheckOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    借用人歸還工具時上傳 Check-out 照片。
    - 後端 AI Gateway 呼叫 Gemini Vision 進行雙圖差分分析。
    - 寬容標準：表面灰塵、水漬、木屑判定為 MATCH。
    - 若 MATCH：狀態變更為 COMPLETED，退回押金，雙方信用分各 +2。
    - 若 MINOR_DIFF 或 DAMAGE_DETECTED：狀態變更為 INSPECTION。
    - 若 confidence < 0.60：回傳 422 IMAGE_TOO_BLURRY 要求重拍。
    """
    order = order_service.get_order(db, current_user, order_id)
    if order.renter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅借用人本人可執行 Check-out 歸還存證。",
        )

    checkout_url = req.image_url or "https://storage.linli-tool.app/checkout/default.jpg"
    gateway = AIGateway.get_instance()

    checkout_image_bytes = None
    if req.image_base64:
        import base64
        b64_str = req.image_base64
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            checkout_image_bytes = base64.b64decode(b64_str)
        except Exception:
            pass

    # 執行差分比對 (注入 SPEC_04 知識庫標準與預期品項)
    tool_id = order.item.damage_tool_id if order.item else None
    expected_name = order.item.name if order.item else "工具歸還"
    evaluation = gateway.compare_checkout_images(
        user_id=current_user.id,
        checkin_image_bytes=None,
        checkout_image_bytes=checkout_image_bytes,
        hint_text=req.notes or checkout_url,
        tool_id=tool_id,
        expected_tool_name=expected_name,
    )

    # 第一道關卡：若判定為非關生活物品或工具調包，阻擋結算推進，要求重新拍照
    eval_result = evaluation.get("result", "MATCH")
    if eval_result in ["INVALID_OBJECT", "TOOL_SWAP_DETECTED"]:
        error_notes = evaluation.get("difference_notes", "歸還照片核驗未通過，請重新拍攝正確工具照片。")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{eval_result}: {error_notes}",
        )

    # 第二道關卡：正常耗損與損壞狀態機推進
    result_data = handover_service.finalize_checkout_order(
        db=db,
        order=order,
        vision_result=eval_result,
        checkout_image_url=checkout_url,
    )

    return CheckOutResponse(
        order_id=order.id,
        status=result_data["status"],
        vision_evaluation=evaluation,
        deposit_refunded=result_data.get("deposit_refunded", 0),
        credit_score_earned=result_data.get("credit_score_earned", 0),
        message=result_data["message"],
    )


