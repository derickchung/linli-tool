import json
from datetime import date, timedelta
import pytest
from backend.models import Community, VerificationStatus, Item, ItemCategory, ItemStatus


@pytest.fixture
def setup_order_env(db_session, create_test_user):
    # Community
    community = Community(name="仁愛敦南豪邸", address="台北市大安區敦化南路一段1號")
    db_session.add(community)
    db_session.commit()
    db_session.refresh(community)

    # Lender (Alex)
    lender, token_lender = create_test_user(
        phone="0988000001",
        name="Alex (出借方)",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    lender.credit_score = 90

    # Renter A: Credit score 105 (Tier A,免押金)
    renter_a, token_renter_a = create_test_user(
        phone="0988000002",
        name="Bob (高分承租)",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    renter_a.credit_score = 105

    # Renter B: Credit score 85 (Tier B,押金半價)
    renter_b, token_renter_b = create_test_user(
        phone="0988000003",
        name="Charlie (一般承租)",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    renter_b.credit_score = 85

    # Renter C: Credit score 70 (Tier C,全額押金)
    renter_c, token_renter_c = create_test_user(
        phone="0988000004",
        name="David (低分承租)",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    renter_c.credit_score = 70

    # Pending User
    pending_user, token_pending = create_test_user(
        phone="0988000005",
        name="Eva (未驗證)",
        status=VerificationStatus.PENDING,
        community_id=community.id,
    )

    db_session.commit()

    # Create 1 Demo Tool (eligible for pool)
    demo_drill = Item(
        owner_id=lender.id,
        community_id=community.id,
        name="Bosch 12V 衝擊電鑽",
        category=ItemCategory.POWER_TOOLS,
        daily_rate=150,
        market_value=3000,
        damage_tool_id="TOOL_DRILL_01",
        status=ItemStatus.AVAILABLE,
    )

    # Create 1 Custom Tool (not eligible for pool)
    custom_saw = Item(
        owner_id=lender.id,
        community_id=community.id,
        name="私人自訂手鋸",
        category=ItemCategory.HAND_TOOLS,
        daily_rate=80,
        market_value=1200,
        damage_tool_id=None,
        status=ItemStatus.AVAILABLE,
    )

    db_session.add_all([demo_drill, custom_saw])
    db_session.commit()
    db_session.refresh(demo_drill)
    db_session.refresh(custom_saw)

    return {
        "community": community,
        "lender": lender,
        "token_lender": token_lender,
        "renter_a": renter_a,
        "token_renter_a": token_renter_a,
        "renter_b": renter_b,
        "token_renter_b": token_renter_b,
        "renter_c": renter_c,
        "token_renter_c": token_renter_c,
        "pending_user": pending_user,
        "token_pending": token_pending,
        "demo_drill": demo_drill,
        "custom_saw": custom_saw,
    }


# ====================================================
# Task 3.1: 租期與押金試算核心 Service & Microcopy
# ====================================================

def test_order_fee_calculation_credit_tiers(client, setup_order_env):
    drill = setup_order_env["demo_drill"]
    token_a = setup_order_env["token_renter_a"]
    token_b = setup_order_env["token_renter_b"]
    token_c = setup_order_env["token_renter_c"]

    start = date.today() + timedelta(days=2)
    end = date.today() + timedelta(days=4)  # 3 days: start, start+1, start+2

    # Tier A: 105 credit score -> deposit = 0
    res_a = client.post(
        "/api/v1/orders/calculate",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["rent_days"] == 3
    assert data_a["total_rent"] == 450  # 150 * 3
    assert data_a["base_deposit"] == 2250  # 150 * 15
    assert data_a["deposit_discount_rate"] == 1.0
    assert data_a["actual_deposit"] == 0
    assert data_a["authorized_total"] == 450
    assert data_a["pool_coverage_applicable"] is True
    assert "授權總額" in data_a["breakdown_title"]
    assert "預授權鎖定" in data_a["cta_button_text"]

    # Tier B: 85 credit score -> deposit = 50%
    res_b = client.post(
        "/api/v1/orders/calculate",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["deposit_discount_rate"] == 0.5
    assert data_b["actual_deposit"] == 1125  # round(2250 * 0.5)
    assert data_b["authorized_total"] == 450 + 1125

    # Tier C: 70 credit score -> deposit = 100%
    res_c = client.post(
        "/api/v1/orders/calculate",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert data_c["deposit_discount_rate"] == 0.0
    assert data_c["actual_deposit"] == 2250
    assert data_c["authorized_total"] == 450 + 2250


# ====================================================
# Task 3.2: 預約下單與並發排他防衝突
# ====================================================

def test_order_creation_and_self_rental_prevention(client, setup_order_env):
    drill = setup_order_env["demo_drill"]
    token_lender = setup_order_env["token_lender"]
    token_renter_a = setup_order_env["token_renter_a"]
    token_pending = setup_order_env["token_pending"]

    start = date.today() + timedelta(days=5)
    end = date.today() + timedelta(days=7)

    # 1. Lender tries to rent their own item -> 400 Bad Request
    res_self = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_lender}"},
    )
    assert res_self.status_code == 400
    assert "自己上架" in res_self.json()["detail"]

    # 2. Pending user tries to rent -> 403 Forbidden
    res_pending = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_pending}"},
    )
    assert res_pending.status_code == 403

    # 3. Validated renter books successfully -> 201 Created
    res_ok = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_renter_a}"},
    )
    assert res_ok.status_code == 201
    data = res_ok.json()
    assert data["status"] == "CONFIRMED"
    assert data["total_rent"] == 450
    assert data["actual_deposit"] == 0
    assert data["order_no"].startswith("ORD")


def test_order_concurrency_conflict_check(client, setup_order_env):
    drill = setup_order_env["demo_drill"]
    token_renter_a = setup_order_env["token_renter_a"]
    token_renter_b = setup_order_env["token_renter_b"]

    base = date.today() + timedelta(days=10)

    # Booking 1: Days 10 to 12
    res1 = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(base), "end_date": str(base + timedelta(days=2))},
        headers={"Authorization": f"Bearer {token_renter_a}"},
    )
    assert res1.status_code == 201

    # Booking 2: Days 11 to 13 (Overlaps Day 11-12) -> 409 Conflict
    res2 = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(base + timedelta(days=1)), "end_date": str(base + timedelta(days=3))},
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    assert res2.status_code == 409
    assert "已被其他鄰居預約" in res2.json()["detail"]

    # Booking 3: Days 12 to 14 (Overlaps Day 12) -> 409 Conflict
    res3 = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(base + timedelta(days=2)), "end_date": str(base + timedelta(days=4))},
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    assert res3.status_code == 409

    # Booking 4: Days 13 to 15 (No overlap) -> 201 Created
    res4 = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(base + timedelta(days=3)), "end_date": str(base + timedelta(days=5))},
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    assert res4.status_code == 201


# ====================================================
# Task 3.3: 取消政策與退費違約金計算
# ====================================================

def test_order_cancellation_policies(client, setup_order_env):
    drill = setup_order_env["demo_drill"]
    token_renter_b = setup_order_env["token_renter_b"]  # Deposit is 1125, rent is 450

    # 1. Order starting 4 days in future (>= 24 hours): Free cancellation
    far_start = date.today() + timedelta(days=4)
    far_end = date.today() + timedelta(days=6)
    res_far = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(far_start), "end_date": str(far_end)},
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    order_far_id = res_far.json()["id"]

    res_cancel_far = client.post(
        f"/api/v1/orders/{order_far_id}/cancel",
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    assert res_cancel_far.status_code == 200
    data_far = res_cancel_far.json()
    assert data_far["status"] == "CANCELLED"
    assert data_far["cancellation_fee"] == 0
    assert data_far["refund_rent"] == 450
    assert data_far["refund_deposit"] == 1125
    assert "全額退還" in data_far["message"]

    # 2. Order starting today (< 24 hours): 20% cancellation fee
    near_start = date.today()
    near_end = date.today() + timedelta(days=2)
    res_near = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(near_start), "end_date": str(near_end)},
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    order_near_id = res_near.json()["id"]

    res_cancel_near = client.post(
        f"/api/v1/orders/{order_near_id}/cancel",
        headers={"Authorization": f"Bearer {token_renter_b}"},
    )
    assert res_cancel_near.status_code == 200
    data_near = res_cancel_near.json()
    assert data_near["status"] == "CANCELLED"
    assert data_near["cancellation_fee"] == round(450 * 0.20)  # 90
    assert data_near["refund_rent"] == 450 - 90  # 360
    assert data_near["refund_deposit"] == 1125  # 100% deposit returned
    assert "20% 租金手續費" in data_near["message"]


# ====================================================
# Task 3.4: 賠償池核心運算與資金帳本
# ====================================================

def test_compensation_pool_and_payout_calculation(client, setup_order_env):
    drill = setup_order_env["demo_drill"]  # Demo tool: market_value = 3000, residual_value = 2100
    saw = setup_order_env["custom_saw"]    # Non-demo tool: market_value = 1200, residual_value = 840
    token_renter_a = setup_order_env["token_renter_a"]  # actual_deposit = 0
    token_renter_c = setup_order_env["token_renter_c"]  # actual_deposit = base_deposit = 2250

    # 1. Pool status query
    res_pool = client.get("/api/v1/orders/pool/status")
    assert res_pool.status_code == 200
    pool_data = res_pool.json()
    assert pool_data["current_balance"] >= 20000
    assert "互助保障池" in pool_data["pool_name"]

    # 2. Demo Tool with MINOR_DIFF (30% liability) and renter actual_deposit = 0
    start = date.today() + timedelta(days=20)
    end = date.today() + timedelta(days=22)
    order_res_a = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_renter_a}"},
    )
    order_id_a = order_res_a.json()["id"]

    comp_res_a = client.post(
        "/api/v1/orders/compensation/calculate",
        json={"order_id": order_id_a, "vision_result": "MINOR_DIFF"},
    )
    assert comp_res_a.status_code == 200
    c_data_a = comp_res_a.json()
    # residual_value = 3000 * 0.70 = 2100
    # liability = 2100 * 0.30 = 630
    assert c_data_a["residual_value"] == 2100
    assert c_data_a["liability"] == 630
    assert c_data_a["renter_out_of_pocket"] == 0  # Deposit was 0
    assert c_data_a["pool_payout"] == 630         # Gap covered by pool
    assert c_data_a["pool_eligible"] is True

    # 3. Demo Tool with DAMAGE_DETECTED (100% liability) and renter actual_deposit = 2250
    start_c = date.today() + timedelta(days=23)
    end_c = date.today() + timedelta(days=25)
    order_res_c = client.post(
        "/api/v1/orders/",
        json={"item_id": drill.id, "start_date": str(start_c), "end_date": str(end_c)},
        headers={"Authorization": f"Bearer {token_renter_c}"},
    )
    order_id_c = order_res_c.json()["id"]

    comp_res_c = client.post(
        "/api/v1/orders/compensation/calculate",
        json={"order_id": order_id_c, "vision_result": "DAMAGE_DETECTED"},
    )
    assert comp_res_c.status_code == 200
    c_data_c = comp_res_c.json()
    # liability = 2100 * 1.0 = 2100
    # deposit was 2250 >= liability
    assert c_data_c["liability"] == 2100
    assert c_data_c["renter_out_of_pocket"] == 2100
    assert c_data_c["pool_payout"] == 0  # Fully covered by deposit, pool does not need to pay

    # 4. Custom tool (Option B fallback, non-demo): pool_eligible = False
    start_saw = date.today() + timedelta(days=26)
    end_saw = date.today() + timedelta(days=28)
    order_res_saw = client.post(
        "/api/v1/orders/",
        json={"item_id": saw.id, "start_date": str(start_saw), "end_date": str(end_saw)},
        headers={"Authorization": f"Bearer {token_renter_a}"},
    )
    order_id_saw = order_res_saw.json()["id"]

    comp_res_saw = client.post(
        "/api/v1/orders/compensation/calculate",
        json={"order_id": order_id_saw, "vision_result": "DAMAGE_DETECTED"},
    )
    assert comp_res_saw.status_code == 200
    c_data_saw = comp_res_saw.json()
    assert c_data_saw["pool_eligible"] is False
    assert c_data_saw["pool_payout"] == 0
    assert "純押金保障模式" in c_data_saw["summary"]


def test_financial_microcopy_compliance(client, setup_order_env):
    """
    PRD 6.3 & Spec 10.3: 嚴格禁止出現「保險」、「保費」、「理賠」等金融保險字眼。
    """
    drill = setup_order_env["demo_drill"]
    token = setup_order_env["token_renter_a"]

    forbidden_keywords = ["保險", "保費", "理賠"]

    # 1. Check Calculate response
    res_calc = client.post(
        "/api/v1/orders/calculate",
        json={
            "item_id": drill.id,
            "start_date": str(date.today() + timedelta(days=1)),
            "end_date": str(date.today() + timedelta(days=3)),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    calc_str = json.dumps(res_calc.json(), ensure_ascii=False)
    for kw in forbidden_keywords:
        assert kw not in calc_str, f"Forbidden term '{kw}' found in calculate response: {calc_str}"

    # 2. Check Pool status response
    res_pool = client.get("/api/v1/orders/pool/status")
    pool_str = json.dumps(res_pool.json(), ensure_ascii=False)
    for kw in forbidden_keywords:
        assert kw not in pool_str, f"Forbidden term '{kw}' found in pool response: {pool_str}"
