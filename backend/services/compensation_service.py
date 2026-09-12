from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from ..models import Order, Item, CompensationLedger
from ..schemas import CompensationCalculateResponse, CompensationPoolStatusResponse

INITIAL_POOL_SEED = 20000  # 社區平台互助保障池預設種子初始基金 (TWD)


def get_current_pool_balance(db: Session) -> Tuple[int, int, int]:
    """
    取得賠償池當前餘額、累計提撥流入、累計補貼支出。
    保證餘額永不為負數。
    """
    last_record = (
        db.query(CompensationLedger)
        .order_by(CompensationLedger.id.desc())
        .first()
    )
    if not last_record:
        # 建立初始種子記錄
        seed_ledger = CompensationLedger(
            order_id=None,
            change_amount=INITIAL_POOL_SEED,
            balance_after=INITIAL_POOL_SEED,
            reason="INITIAL_COMMUNITY_SEED",
            notes="平台冷啟動損壞互助保障種子基金",
        )
        db.add(seed_ledger)
        db.commit()
        db.refresh(seed_ledger)
        return INITIAL_POOL_SEED, INITIAL_POOL_SEED, 0

    current_balance = last_record.balance_after

    inflow = (
        db.query(func.sum(CompensationLedger.change_amount))
        .filter(CompensationLedger.change_amount > 0)
        .scalar()
        or 0
    )
    outflow_raw = (
        db.query(func.sum(CompensationLedger.change_amount))
        .filter(CompensationLedger.change_amount < 0)
        .scalar()
        or 0
    )
    total_outflow = abs(outflow_raw)

    return current_balance, inflow, total_outflow


def contribute_to_pool(
    db: Session,
    amount: int,
    order_id: Optional[int] = None,
    reason: str = "PLATFORM_FEE_CONTRIBUTION",
    notes: Optional[str] = None,
) -> int:
    """每筆順利結案訂單提撥入池"""
    if amount <= 0:
        return 0
    current_balance, _, _ = get_current_pool_balance(db)
    new_balance = current_balance + amount

    ledger = CompensationLedger(
        order_id=order_id,
        change_amount=amount,
        balance_after=new_balance,
        reason=reason,
        notes=notes,
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return new_balance


def payout_from_pool(
    db: Session,
    requested_amount: int,
    order_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """
    從互助保障池撥付補貼。
    落實不透支防護原則：若餘額不足，實際撥付額降為當前餘額，餘額不為負數。
    """
    if requested_amount <= 0:
        return 0

    current_balance, _, _ = get_current_pool_balance(db)
    actual_payout = min(requested_amount, current_balance)

    if actual_payout > 0:
        new_balance = current_balance - actual_payout
        ledger = CompensationLedger(
            order_id=order_id,
            change_amount=-actual_payout,
            balance_after=new_balance,
            reason="DAMAGE_COMPENSATION_PAYOUT",
            notes=notes or f"訂單 #{order_id} 工具損壞互助補貼支出",
        )
        db.add(ledger)
        db.commit()

    return actual_payout


def calculate_compensation(
    db: Session,
    order_id: int,
    vision_result: str,
) -> CompensationCalculateResponse:
    """
    核心損壞補貼與責任計算引擎 (SPEC_03)
    嚴格遵守微文案合規：禁止使用「保險」、「保費」、「理賠」等字眼。
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到訂單 ID: {order_id}",
        )

    item = order.item
    # 1. 殘值 = 原價 * 70%
    residual_value = round(item.market_value * 0.70)

    v_upper = vision_result.upper()
    if v_upper == "MINOR_DIFF":
        damage_ratio = 0.30
    elif v_upper == "DAMAGE_DETECTED":
        damage_ratio = 1.00
    else:
        damage_ratio = 0.0

    # 2. 應賠金額
    liability = round(residual_value * damage_ratio)

    # 3. 示範工具判斷 (Option B: 非示範工具回退純押金制)
    pool_eligible = bool(item.damage_tool_id)

    if not pool_eligible:
        # 純押金制：借用人自付上限為已繳實際押金，保障池不撥付
        renter_out_of_pocket = min(liability, order.actual_deposit)
        pool_payout = 0
        summary = (
            f"此工具為住戶自訂上架項目（非示範規格），採純押金保障模式。"
            f"評估應負擔補償 NT$ {liability}，由實收押金 NT$ {order.actual_deposit} 抵扣 NT$ {renter_out_of_pocket}。"
        )
    else:
        # 示範工具互助保障制
        renter_out_of_pocket = min(liability, order.actual_deposit)
        gap = max(0, liability - order.actual_deposit)
        current_balance, _, _ = get_current_pool_balance(db)
        # 賠償池撥付額 (受限於池內餘額，不透支)
        pool_payout = min(gap, current_balance)

        if gap > 0 and pool_payout < gap:
            summary = (
                f"經檢測工具損壞比例為 {int(damage_ratio * 100)}%，核算應賠金額 NT$ {liability}。"
                f"已抵扣借用人押金 NT$ {renter_out_of_pocket}，互助保障池因當前餘額上限撥付 NT$ {pool_payout}。"
            )
        else:
            summary = (
                f"經檢測工具損壞比例為 {int(damage_ratio * 100)}%，核算應賠金額 NT$ {liability}。"
                f"借用人履約押金抵扣 NT$ {renter_out_of_pocket}，平台損壞互助保障補貼支出 NT$ {pool_payout}，完整保障出借方權益。"
            )

    return CompensationCalculateResponse(
        order_id=order.id,
        item_name=item.name,
        market_value=item.market_value,
        residual_value=residual_value,
        vision_result=v_upper,
        damage_ratio=damage_ratio,
        liability=liability,
        actual_deposit=order.actual_deposit,
        pool_eligible=pool_eligible,
        pool_payout=pool_payout,
        renter_out_of_pocket=renter_out_of_pocket,
        summary=summary,
    )
