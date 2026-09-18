import uuid
from datetime import date, datetime, time as dt_time, timezone, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, not_

from ..models import Order, Item, User, OrderStatus, VerificationStatus, ItemStatus
from ..schemas import (
    OrderCalculateResponse,
    OrderResponse,
    OrderCancelResponse,
)


def calculate_fees(
    daily_rate: int,
    credit_score: int,
    start_date: date,
    end_date: date,
) -> dict:
    rent_days = (end_date - start_date).days + 1
    total_rent = daily_rate * rent_days
    base_deposit = daily_rate * 15

    if credit_score >= 100:
        deposit_discount_rate = 1.0
        actual_deposit = 0
    elif credit_score >= 80:
        deposit_discount_rate = 0.5
        actual_deposit = round(base_deposit * 0.5)
    else:
        deposit_discount_rate = 0.0
        actual_deposit = base_deposit

    authorized_total = total_rent + actual_deposit

    return {
        "rent_days": rent_days,
        "daily_rate": daily_rate,
        "total_rent": total_rent,
        "base_deposit": base_deposit,
        "deposit_discount_rate": deposit_discount_rate,
        "actual_deposit": actual_deposit,
        "authorized_total": authorized_total,
    }


def to_order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        item_id=order.item_id,
        item_name=order.item.name if order.item else None,
        renter_id=order.renter_id,
        renter_name=order.renter.name if order.renter else None,
        lender_id=order.lender_id,
        lender_name=order.lender.name if order.lender else None,
        start_date=order.start_date,
        end_date=order.end_date,
        rent_days=order.rent_days,
        daily_rate=order.daily_rate,
        total_rent=order.total_rent,
        base_deposit=order.base_deposit,
        actual_deposit=order.actual_deposit,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        checkin_image_url=order.checkin_image_url,
        checkout_image_url=order.checkout_image_url,
        vision_result=order.vision_result,
        compensation_amount=order.compensation_amount or 0,
        pool_payout=order.pool_payout or 0,
        created_at=order.created_at,
    )


def calculate_order_fee(
    db: Session,
    user: User,
    item_id: int,
    start_date: date,
    end_date: date,
) -> OrderCalculateResponse:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="歸還日期 end_date 不得早於起租日期 start_date",
        )

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到工具 ID: {item_id}",
        )

    if user.community_id and user.community_id != item.community_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="跨社區資料隔離保護：無法試算非所屬社區工具之租期費用",
        )

    fees = calculate_fees(item.daily_rate, user.credit_score, start_date, end_date)

    return OrderCalculateResponse(
        item_id=item.id,
        item_name=item.name,
        rent_days=fees["rent_days"],
        daily_rate=fees["daily_rate"],
        total_rent=fees["total_rent"],
        base_deposit=fees["base_deposit"],
        user_credit_score=user.credit_score,
        deposit_discount_rate=fees["deposit_discount_rate"],
        actual_deposit=fees["actual_deposit"],
        authorized_total=fees["authorized_total"],
        pool_coverage_applicable=bool(item.damage_tool_id),
    )


def create_order(
    db: Session,
    user: User,
    item_id: int,
    start_date: date,
    end_date: date,
) -> Order:
    if user.verification_status != VerificationStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅已完成社區驗證之住戶具備預約工具權限。",
        )
    if not user.community_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="住戶尚未加入所屬社區，無法預約工具。",
        )
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="歸還日期 end_date 不得早於起租日期 start_date",
        )

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到工具 ID: {item_id}",
        )

    # 1. 跨社區隔離檢核
    if user.community_id != item.community_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="跨社區資料隔離保護：無法預約非所屬社區之工具。",
        )

    # 2. 禁止借用自己上架的工具
    if item.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無法預約租借自己上架的工具。",
        )

    # 3. 並發排他衝突檢核 (Concurrency Control)
    conflict = (
        db.query(Order)
        .filter(
            Order.item_id == item_id,
            Order.status.in_([
                OrderStatus.CONFIRMED,
                OrderStatus.PICKED_UP,
                OrderStatus.IN_USE,
            ]),
            not_(or_(Order.end_date < start_date, Order.start_date > end_date)),
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="該工具在所選時段已被其他鄰居預約，請選擇其他日期或工具。",
        )

    # 4. 費用計算
    fees = calculate_fees(item.daily_rate, user.credit_score, start_date, end_date)

    order_no = f"ORD{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    order = Order(
        order_no=order_no,
        item_id=item.id,
        renter_id=user.id,
        lender_id=item.owner_id,
        start_date=start_date,
        end_date=end_date,
        rent_days=fees["rent_days"],
        daily_rate=fees["daily_rate"],
        total_rent=fees["total_rent"],
        base_deposit=fees["base_deposit"],
        actual_deposit=fees["actual_deposit"],
        status=OrderStatus.CONFIRMED,
        checkin_image_url=item.image_url or "/test_assets/drill_checkin.jpg",
    )

    # 同步更新工具庫存狀態為 RENTED (出借中/已預約)
    item.status = ItemStatus.RENTED
    db.add(item)
    db.add(order)
    db.commit()
    db.refresh(order)
    db.refresh(item)
    return order


def cancel_order(
    db: Session,
    user: User,
    order_id: int,
) -> OrderCancelResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到訂單 ID: {order_id}",
        )

    # 僅限承租人或出借人可發起取消
    if user.id not in [order.renter_id, order.lender_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您無權限取消此筆訂單。",
        )

    # 僅在未取件前 (PENDING, CONFIRMED) 允許取消
    if order.status not in [OrderStatus.CONFIRMED, OrderStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂單目前處於 {order.status.value} 狀態，無法執行線上取消。",
        )

    # 計算起租時間差 (以起租日 00:00:00 UTC 為基準點)
    start_datetime = datetime.combine(order.start_date, dt_time.min, tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    remaining_seconds = (start_datetime - now_utc).total_seconds()
    hours_before_start = remaining_seconds / 3600.0

    if hours_before_start >= 24.0:
        # 免費取消 (>= 24小時)
        cancellation_fee = 0
        refund_rent = order.total_rent
        refund_deposit = order.actual_deposit
        message = (
            f"於起租前 {hours_before_start:.1f} 小時取消（滿 24 小時免費取消期），"
            f"全額退還租金 NT$ {refund_rent} 與押金 NT$ {refund_deposit}。"
        )
    else:
        # 收取 20% 租金違約金 (< 24小時)
        cancellation_fee = round(order.total_rent * 0.20)
        refund_rent = order.total_rent - cancellation_fee
        refund_deposit = order.actual_deposit
        message = (
            f"於起租前 {max(0.0, hours_before_start):.1f} 小時取消（不足 24 小時），"
            f"依約定收取 20% 租金手續費 NT$ {cancellation_fee} 補貼出借鄰居，"
            f"退還剩餘租金 NT$ {refund_rent} 及押金 NT$ {refund_deposit}。"
        )

    order.status = OrderStatus.CANCELLED

    # 檢查該工具是否仍有其他進行中之有效訂單，若無則將道具狀態復原為 AVAILABLE (可借用)
    other_active = (
        db.query(Order)
        .filter(
            Order.item_id == order.item_id,
            Order.id != order.id,
            Order.status.in_([
                OrderStatus.CONFIRMED,
                OrderStatus.PICKED_UP,
                OrderStatus.IN_USE,
                OrderStatus.INSPECTION,
                OrderStatus.DISPUTED,
            ]),
        )
        .first()
    )
    if not other_active:
        item = db.query(Item).filter(Item.id == order.item_id).first()
        if item:
            item.status = ItemStatus.AVAILABLE
            db.add(item)

    db.commit()
    db.refresh(order)

    return OrderCancelResponse(
        order_id=order.id,
        status="CANCELLED",
        hours_before_start=round(hours_before_start, 2),
        cancellation_fee=cancellation_fee,
        refund_rent=refund_rent,
        refund_deposit=refund_deposit,
        message=message,
    )


def get_order(db: Session, user: User, order_id: int) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到訂單 ID: {order_id}",
        )
    if user.id not in [order.renter_id, order.lender_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您無權限查看此訂單明細。",
        )
    return order


def list_user_orders(
    db: Session,
    user: User,
    role: Optional[str] = None,
) -> List[Order]:
    q = db.query(Order)
    if role == "renter":
        q = q.filter(Order.renter_id == user.id)
    elif role == "lender":
        q = q.filter(Order.lender_id == user.id)
    else:
        q = q.filter(or_(Order.renter_id == user.id, Order.lender_id == user.id))

    return q.order_by(Order.id.desc()).all()
