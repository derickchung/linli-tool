from datetime import date, timedelta
import pytest
from backend.models import Community, VerificationStatus, Item, ItemCategory, ItemStatus, OrderStatus
from backend.services.handover_service import finalize_checkout_order


@pytest.fixture
def setup_handover_env(db_session, create_test_user):
    community = Community(name="信義富邦社區", address="台北市信義區松勇路1號")
    db_session.add(community)
    db_session.commit()
    db_session.refresh(community)

    # Lender
    lender, token_lender = create_test_user(
        phone="0977000001",
        name="Lender住戶",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    lender.credit_score = 80

    # Renter
    renter, token_renter = create_test_user(
        phone="0977000002",
        name="Renter住戶",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )
    renter.credit_score = 80

    # Stranger (different user)
    stranger, token_stranger = create_test_user(
        phone="0977000003",
        name="Stranger住戶",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )

    drill = Item(
        owner_id=lender.id,
        community_id=community.id,
        name="Bosch 衝擊電鑽",
        category=ItemCategory.POWER_TOOLS,
        daily_rate=150,
        market_value=3000,
        damage_tool_id="TOOL_DRILL_01",
        status=ItemStatus.AVAILABLE,
    )
    db_session.add(drill)
    db_session.commit()
    db_session.refresh(drill)

    # Create an initial order in CONFIRMED state
    start = date.today()
    end = date.today() + timedelta(days=2)

    return {
        "community": community,
        "lender": lender,
        "token_lender": token_lender,
        "renter": renter,
        "token_renter": token_renter,
        "stranger": stranger,
        "token_stranger": token_stranger,
        "drill": drill,
        "start": start,
        "end": end,
    }


def test_totp_code_generation_and_pickup_verification(client, setup_handover_env):
    drill = setup_handover_env["drill"]
    token_renter = setup_handover_env["token_renter"]
    token_lender = setup_handover_env["token_lender"]
    token_stranger = setup_handover_env["token_stranger"]

    # 1. Renter books tool -> status CONFIRMED
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(setup_handover_env["start"]),
            "end_date": str(setup_handover_env["end"]),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_book.status_code == 201
    order_id = res_book.json()["id"]

    # 2. Stranger tries to get handover code -> 403 Forbidden
    res_bad_code = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_stranger}"},
    )
    assert res_bad_code.status_code == 403

    # 3. Renter gets handover code -> 6-digit TOTP
    res_code = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_code.status_code == 200
    code_data = res_code.json()
    totp_code = code_data["handover_code"]
    assert len(totp_code) == 6
    assert totp_code.isdigit()
    assert 0 < code_data["expires_in_seconds"] <= 60
    assert f"order_id={order_id}" in code_data["qr_payload"]

    # 4. Lender tries wrong code -> 400 Bad Request
    res_bad_verify = client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": "000000" if totp_code != "000000" else "111111"},
        headers={"Authorization": f"Bearer {token_lender}"},
    )
    assert res_bad_verify.status_code == 400
    assert "取件核銷碼錯誤" in res_bad_verify.json()["detail"]

    # 5. Lender verifies with correct code -> status PICKED_UP
    res_verify = client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": totp_code},
        headers={"Authorization": f"Bearer {token_lender}"},
    )
    assert res_verify.status_code == 200
    assert res_verify.json()["status"] == "PICKED_UP"


def test_checkin_hash_and_status_advance(client, setup_handover_env):
    drill = setup_handover_env["drill"]
    token_renter = setup_handover_env["token_renter"]
    token_lender = setup_handover_env["token_lender"]

    # 1. Create order and verify pickup
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(setup_handover_env["start"]),
            "end_date": str(setup_handover_env["end"]),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    code_res = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    totp_code = code_res.json()["handover_code"]

    client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": totp_code},
        headers={"Authorization": f"Bearer {token_lender}"},
    )

    # 2. Check-in photo with SHA-256 checksum -> status IN_USE
    res_checkin = client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={
            "image_url": "https://storage.linli-tool.app/checkin/test_photo_1.jpg",
            "notes": "手把側面有些許正常擦傷，功能運作正常。",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_checkin.status_code == 200
    c_data = res_checkin.json()
    assert c_data["status"] == "IN_USE"
    assert len(c_data["checksum_sha256"]) == 64  # SHA-256 length
    assert "狸利" in c_data["microcopy_guide"]


def test_checkout_match_completion_and_credit_reward(client, db_session, setup_handover_env):
    drill = setup_handover_env["drill"]
    token_renter = setup_handover_env["token_renter"]
    renter = setup_handover_env["renter"]
    lender = setup_handover_env["lender"]

    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(setup_handover_env["start"]),
            "end_date": str(setup_handover_env["end"]),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    from backend.models import Order
    order = db_session.query(Order).filter(Order.id == order_id).first()

    # Simulate Checkout MATCH
    checkout_result = finalize_checkout_order(
        db=db_session,
        order=order,
        vision_result="MATCH",
        checkout_image_url="https://storage.linli-tool.app/checkout/test_match.jpg",
    )
    assert checkout_result["status"] == "COMPLETED"
    assert checkout_result["credit_score_earned"] == 2

    # Verify both users gained +2 credit score (80 -> 82)
    db_session.refresh(renter)
    db_session.refresh(lender)
    assert renter.credit_score == 82
    assert lender.credit_score == 82


def test_dispute_ticket_workflow(client, db_session, setup_handover_env):
    drill = setup_handover_env["drill"]
    token_renter = setup_handover_env["token_renter"]
    token_lender = setup_handover_env["token_lender"]
    token_stranger = setup_handover_env["token_stranger"]

    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(setup_handover_env["start"]),
            "end_date": str(setup_handover_env["end"]),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    # 1. Renter creates dispute ticket -> order status DISPUTED
    res_dispute = client.post(
        "/api/v1/disputes/",
        json={
            "order_id": order_id,
            "reason": "AI 差分判定為 MINOR_DIFF，但表面痕跡為取件前即存在之舊傷，Check-in 照片可見。",
            "evidence_photos": ["https://storage.linli-tool.app/evidence/close_up.jpg"],
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_dispute.status_code == 201
    dispute_id = res_dispute.json()["id"]
    assert res_dispute.json()["status"] == "OPEN"

    # Verify order status became DISPUTED
    from backend.models import Order
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order.status.value == "DISPUTED"

    # 2. Prevent duplicate dispute
    res_dup = client.post(
        "/api/v1/disputes/",
        json={"order_id": order_id, "reason": "重複發起申訴"},
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_dup.status_code == 409

    # 3. Query dispute details
    res_get = client.get(
        f"/api/v1/disputes/{dispute_id}",
        headers={"Authorization": f"Bearer {token_lender}"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["order_id"] == order_id
    assert len(res_get.json()["evidence_photos"]) == 1

    # 4. Stranger cannot view dispute -> 403
    res_stranger = client.get(
        f"/api/v1/disputes/{dispute_id}",
        headers={"Authorization": f"Bearer {token_stranger}"},
    )
    assert res_stranger.status_code == 403

    # 5. Resolve dispute -> status RESOLVED, order status COMPLETED
    res_resolve = client.patch(
        f"/api/v1/disputes/{dispute_id}/resolve",
        json={"status": "RESOLVED", "resolution_notes": "經人工核對 Check-in 存證照片，確認該痕跡為既有舊傷，判定屬實結案。"},
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "RESOLVED"
    db_session.refresh(order)
    assert order.status.value == "COMPLETED"
