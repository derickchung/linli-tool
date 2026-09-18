from datetime import date, timedelta
import pytest
from backend.models import Community, VerificationStatus, Item, ItemCategory, ItemStatus
from backend.ai.gateway import AIGateway


@pytest.fixture
def setup_ai_env(db_session, create_test_user):
    community = Community(name="信義聯勤社區", address="台北市大安區建國南路二段100號")
    db_session.add(community)
    db_session.commit()
    db_session.refresh(community)

    user1, token1 = create_test_user(
        phone="0966000001",
        name="AI測試員",
        status=VerificationStatus.VALIDATED,
        community_id=community.id,
    )

    drill = Item(
        owner_id=user1.id,
        community_id=community.id,
        name="Bosch 衝擊電鑽組",
        category=ItemCategory.POWER_TOOLS,
        daily_rate=150,
        market_value=3000,
        damage_tool_id="TOOL_DRILL_01",
        safety_notes="水泥牆打孔請配戴護目鏡",
        status=ItemStatus.AVAILABLE,
    )
    db_session.add(drill)
    db_session.commit()
    db_session.refresh(drill)

    # Clear gateway cache and rate limit history before each test
    gw = AIGateway.get_instance()
    gw.rate_limits.clear()
    gw.prompt_cache.clear()

    return {
        "community": community,
        "user1": user1,
        "token1": token1,
        "drill": drill,
    }


def test_a2_scenario_recommendation_and_fallbacks(client, setup_ai_env):
    token = setup_ai_env["token1"]

    # 1. Normal tool repair query
    res_normal = client.post(
        "/api/v1/rag/recommend",
        json={"prompt": "客廳水泥牆想要安裝貓跳台跟層板，該用甚麼工具？"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_normal.status_code == 200
    data_normal = res_normal.json()
    assert any("電鑽" in t for t in data_normal["tags"])
    assert len(data_normal["matched_item_ids"]) >= 1
    assert setup_ai_env["drill"].id in data_normal["matched_item_ids"]

    # 2. Out-of-domain query (Fallback 4: Mascot LiLi polite decline)
    res_out = client.post(
        "/api/v1/rag/recommend",
        json={"prompt": "明天總統大選八卦跟股市名牌"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_out.status_code == 200
    data_out = res_out.json()
    assert len(data_out["tags"]) == 0
    assert "狸利" in data_out["advice"]
    assert "只擅長工具租借與居家修繕" in data_out["advice"]


def test_d1_tool_image_recognition_and_price_omission(client, setup_ai_env):
    token = setup_ai_env["token1"]

    # Recognize tool from hint/image
    res = client.post(
        "/api/v1/items/recognize?filename_hint=high_pressure_washer.jpg",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "清洗機" in data["suggested_name"]
    assert data["category"] == "CLEANING"
    assert data["damage_tool_id_match"] == "TOOL_WASHER_01"
    assert len(data["suggested_accessories"]) >= 2
    assert "安全" in data["safety_warning"]

    # Strict compliance: D1 MUST NOT return market_value or daily_rate
    assert "market_value" not in data
    assert "daily_rate" not in data


def test_checkout_image_difference_and_tolerance(client, setup_ai_env, create_test_user):
    drill = setup_ai_env["drill"]
    user1 = setup_ai_env["user1"]
    renter, token_renter = create_test_user(
        phone="0966000002",
        name="承租人",
        status=VerificationStatus.VALIDATED,
        community_id=setup_ai_env["community"].id,
    )

    # Book and check-in
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=2)),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    # Verify handover
    code_res = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": code_res.json()["handover_code"]},
        headers={"Authorization": f"Bearer {setup_ai_env['token1']}"},
    )

    # Check-in
    client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={"image_url": "https://storage.linli-tool.app/checkin/init.jpg"},
        headers={"Authorization": f"Bearer {token_renter}"},
    )

    # Scenario 1: Normal dust / wear -> MATCH
    res_match = client.post(
        f"/api/v1/orders/{order_id}/check-out",
        json={
            "image_url": "https://storage.linli-tool.app/checkout/clean.jpg",
            "notes": "外表無損，正常使用木屑粉塵",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_match.status_code == 200
    data_match = res_match.json()
    assert data_match["status"] == "COMPLETED"
    assert data_match["vision_evaluation"]["result"] == "MATCH"
    assert data_match["credit_score_earned"] == 2


def test_checkout_image_too_blurry_rejection(client, setup_ai_env, create_test_user):
    drill = setup_ai_env["drill"]
    renter, token_renter = create_test_user(
        phone="0966000003",
        name="模糊拍照者",
        status=VerificationStatus.VALIDATED,
        community_id=setup_ai_env["community"].id,
    )

    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(date.today() + timedelta(days=1)),
            "end_date": str(date.today() + timedelta(days=3)),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    # When photo is blurry (confidence < 0.60), expect 422
    res_blurry = client.post(
        f"/api/v1/orders/{order_id}/check-out",
        json={
            "image_url": "https://storage.linli-tool.app/checkout/blurry.jpg",
            "notes": "模糊 photo blurry",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_blurry.status_code == 422
    assert "IMAGE_TOO_BLURRY" in res_blurry.json()["detail"]


def test_ai_gateway_rate_limiting_and_caching(client, setup_ai_env):
    token = setup_ai_env["token1"]
    gw = AIGateway.get_instance()
    gw.rate_limits.clear()
    gw.prompt_cache.clear()

    # Call 5 times (allowed)
    for i in range(5):
        res = client.post(
            "/api/v1/rag/recommend",
            json={"prompt": f"水管漏水活動扳手 {i}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

    # 6th call within same minute -> 429 Too Many Requests
    res_limited = client.post(
        "/api/v1/rag/recommend",
        json={"prompt": "水管漏水第6次查詢"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_limited.status_code == 429
    assert "頻率已達上限" in res_limited.json()["detail"]


def test_tool_consistency_verification(client, setup_ai_env):
    token = setup_ai_env["token1"]

    # 1. Matching tool (Drill photo for Drill tool) -> Consistent
    res_match = client.post(
        "/api/v1/items/verify-consistency",
        json={
            "expected_name": "BOSCH GSB 185-LI 震動電鑽",
            "expected_category": "POWER_TOOLS",
            "filename_hint": "bosch_drill.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_match.status_code == 200
    data_match = res_match.json()
    assert data_match["is_consistent"] is True
    assert data_match["requires_retake"] is False
    assert data_match["token_cost_estimate"] <= 258

    # 2. Mismatched tool (Ladder photo for Drill tool) -> Inconsistent, requires retake
    res_mismatch = client.post(
        "/api/v1/items/verify-consistency",
        json={
            "expected_name": "BOSCH 震動電鑽",
            "expected_category": "POWER_TOOLS",
            "filename_hint": "ladder_aframe.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_mismatch.status_code == 200
    data_mismatch = res_mismatch.json()
    assert data_mismatch["is_consistent"] is False
    assert data_mismatch["requires_retake"] is True
    assert "不符" in data_mismatch["mismatch_reason"] or "梯" in data_mismatch["mismatch_reason"]

    # 3. Blurry photo -> Rejection and requires retake
    res_blurry = client.post(
        "/api/v1/items/verify-consistency",
        json={
            "expected_name": "BOSCH 震動電鑽",
            "expected_category": "POWER_TOOLS",
            "filename_hint": "photo_blurry.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_blurry.status_code == 200
    data_blurry = res_blurry.json()
    assert data_blurry["is_consistent"] is False
    assert data_blurry["requires_retake"] is True


def test_checkin_same_object_verification_and_mismatch_rejection(client, setup_ai_env, create_test_user):
    drill = setup_ai_env["drill"]
    renter, token_renter = create_test_user(
        phone="0977888999",
        name="測試租客",
        status=VerificationStatus.VALIDATED,
        community_id=setup_ai_env["community"].id,
    )

    # 1. Book and verify pickup
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=2)),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    code_res = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": code_res.json()["handover_code"]},
        headers={"Authorization": f"Bearer {setup_ai_env['token1']}"},
    )

    # 2. Check-in with mismatched photo (Ladder instead of Drill) -> Expect 422 MISMATCH_TOOL
    res_mismatch = client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={
            "image_url": "https://storage.linli-tool.app/checkin/mismatch_ladder.jpg",
            "notes": "ladder mismatch test diff",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_mismatch.status_code == 422
    assert "MISMATCH_TOOL" in res_mismatch.json()["detail"]

    # 3. Check-in with matching photo -> Success 200 and status IN_USE
    res_correct = client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={
            "image_url": "https://storage.linli-tool.app/checkin/drill_same.jpg",
            "notes": "正常相同物件",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_correct.status_code == 200
    c_data = res_correct.json()
    assert c_data["status"] == "IN_USE"
    assert c_data["is_same_object"] is True


def test_multi_brand_drill_recognition_and_consistency(client, setup_ai_env):
    token = setup_ai_env["token1"]
    gw = AIGateway.get_instance()

    # 1. Multi-brand Drill D1 Recognition
    brands = [
        ("drill_makita.jpg", "Makita", "牧田"),
        ("drill_dewalt.jpg", "DeWalt", "得偉"),
        ("drill_milwaukee.jpg", "Milwaukee", "美沃奇"),
        ("drill_bosch.jpg", "Bosch", "GSB"),
    ]
    for filename, brand_en, brand_zh in brands:
        gw.rate_limits.clear()
        res = client.post(
            f"/api/v1/items/recognize?filename_hint={filename}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert brand_en in data["suggested_name"] or brand_zh in data["suggested_name"]
        assert data["category"] == "POWER_TOOLS"
        assert len(data["suggested_accessories"]) >= 2

    # 2. Multi-brand Drill Consistency Check (All 4 brands are valid drills)
    for filename, brand_en, _ in brands:
        gw.rate_limits.clear()
        res_c = client.post(
            "/api/v1/items/verify-consistency",
            json={
                "expected_name": f"{brand_en} 震動電鑽",
                "expected_category": "POWER_TOOLS",
                "filename_hint": filename,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_c.status_code == 200
        data_c = res_c.json()
        assert data_c["is_consistent"] is True
        assert data_c["requires_retake"] is False

    # 3. Unrelated everyday item (Coffee Mug) consistency check -> REJECT
    gw.rate_limits.clear()
    res_mug = client.post(
        "/api/v1/items/verify-consistency",
        json={
            "expected_name": "Bosch 衝擊電鑽",
            "expected_category": "POWER_TOOLS",
            "filename_hint": "unrelated_coffee_mug.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # 4. Unknown/Unrecognized Tool -> Does NOT default to Bosch, returns empty suggested_name
    gw.rate_limits.clear()
    res_unknown = client.post(
        "/api/v1/items/recognize?filename_hint=custom_photo_123.jpg",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_unknown.status_code == 200
    data_unknown = res_unknown.json()
    assert data_unknown["suggested_name"] == ""
    assert data_unknown.get("is_recognized") is False
    assert "Bosch" not in data_unknown["suggested_name"]
    assert "手動" in data_unknown["safety_warning"]

    # 5. User Manually inputs tool name (e.g. DeWalt) and verifies consistency -> Accepted
    gw.rate_limits.clear()
    res_manual = client.post(
        "/api/v1/items/verify-consistency",
        json={
            "expected_name": "DeWalt 得偉 20V 雙速震動電鑽",
            "expected_category": "POWER_TOOLS",
            "filename_hint": "custom_photo_123.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_manual.status_code == 200
    data_manual = res_manual.json()
    assert data_manual["is_consistent"] is True
    assert data_manual["requires_retake"] is False



def test_same_object_cross_brand_swap_prevention(client, setup_ai_env, create_test_user):
    drill = setup_ai_env["drill"]  # Bosch drill
    renter, token_renter = create_test_user(
        phone="0988777666",
        name="品牌測試租客",
        status=VerificationStatus.VALIDATED,
        community_id=setup_ai_env["community"].id,
    )

    # Book and verify pickup
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=1)),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    code_res = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": code_res.json()["handover_code"]},
        headers={"Authorization": f"Bearer {setup_ai_env['token1']}"},
    )

    # Check-in with Makita drill when order is Bosch drill -> REJECT brand swap!
    res_swap = client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={
            "image_url": "https://storage.linli-tool.app/checkin/drill_makita.jpg",
            "notes": "makita drill brand swap test",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_swap.status_code == 422
    assert "MISMATCH_TOOL" in res_swap.json()["detail"]

    # Check-in with coffee mug -> REJECT non-tool!
    res_mug = client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={
            "image_url": "https://storage.linli-tool.app/checkin/unrelated_coffee_mug.jpg",
            "notes": "coffee mug unrelated test",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_mug.status_code == 422


def test_checkout_unrelated_image_and_tool_swap_rejection(client, setup_ai_env, create_test_user):
    drill = setup_ai_env["drill"]
    renter, token_renter = create_test_user(
        phone="0911222333",
        name="歸還測試租客",
        status=VerificationStatus.VALIDATED,
        community_id=setup_ai_env["community"].id,
    )

    # Order lifecycle to IN_USE
    res_book = client.post(
        "/api/v1/orders/",
        json={
            "item_id": drill.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=1)),
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    order_id = res_book.json()["id"]

    code_res = client.get(
        f"/api/v1/orders/{order_id}/handover/code",
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    client.post(
        f"/api/v1/orders/{order_id}/handover/verify",
        json={"code": code_res.json()["handover_code"]},
        headers={"Authorization": f"Bearer {setup_ai_env['token1']}"},
    )
    client.post(
        f"/api/v1/orders/{order_id}/check-in",
        json={"image_url": "https://storage.linli-tool.app/checkin/drill_bosch_same.jpg", "notes": "正常相同物件"},
        headers={"Authorization": f"Bearer {token_renter}"},
    )

    # 1. Return Checkout with UNRELATED non-tool image (Coffee Mug) -> Must fail with 422 INVALID_OBJECT!
    res_mug_checkout = client.post(
        f"/api/v1/orders/{order_id}/check-out",
        json={
            "image_url": "https://storage.linli-tool.app/checkout/unrelated_coffee_mug.jpg",
            "notes": "歸還拍攝馬克杯 coffee mug",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_mug_checkout.status_code == 422
    assert "INVALID_OBJECT" in res_mug_checkout.json()["detail"]

    # 2. Return Checkout with SWAPPED TOOL (Makita drill instead of Bosch drill) -> Must fail with 422 TOOL_SWAP_DETECTED!
    res_swap_checkout = client.post(
        f"/api/v1/orders/{order_id}/check-out",
        json={
            "image_url": "https://storage.linli-tool.app/checkout/drill_makita.jpg",
            "notes": "調包歸還牧田 swap makita",
        },
        headers={"Authorization": f"Bearer {token_renter}"},
    )
    assert res_swap_checkout.status_code == 422
    assert "TOOL_SWAP_DETECTED" in res_swap_checkout.json()["detail"]

    # 3. Direct AI Gateway check returns recommended angle guidance
    gw = AIGateway.get_instance()
    res_gw = gw.compare_checkout_images(
        user_id=renter.id,
        checkin_image_bytes=None,
        checkout_image_bytes=None,
        hint_text="unrelated_coffee_mug.jpg",
        expected_tool_name="Bosch 衝擊電鑽組",
    )
    assert res_gw["result"] == "INVALID_OBJECT"
    assert res_gw["requires_retake"] is True
    assert "recommended_angle" in res_gw
    assert "45" in res_gw["recommended_angle"]


def test_items_verify_same_object_endpoint(client, setup_ai_env):
    """驗證前端 Check-in 專用之 /api/v1/items/verify-same-object 端點"""
    token = setup_ai_env["token1"]
    gw = AIGateway.get_instance()

    # 1. 現場取件拍攝非關雜物 (馬克杯) ➔ 必須即時攔截判定為不同物件且需要重拍！
    gw.rate_limits.clear()
    res_mug = client.post(
        "/api/v1/items/verify-same-object",
        json={
            "item_name": "BOSCH GSB 185-LI 18V免碳刷震動電鑽",
            "original_image_url": "/test_assets/drill_checkin.jpg",
            "filename_hint": "unrelated_coffee_mug.jpg 咖啡馬克杯",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_mug.status_code == 200
    data_mug = res_mug.json()
    assert data_mug["is_same_object"] is False
    assert data_mug["requires_retake"] is True
    assert "馬克杯" in data_mug["difference_notes"] or "生活" in data_mug["difference_notes"]
    assert "recommended_angle" in data_mug

    # 2. 現場取件拍攝同類跨品牌 (牧田電鑽冒充 Bosch) ➔ 必須攔截調包！
    gw.rate_limits.clear()
    res_swap = client.post(
        "/api/v1/items/verify-same-object",
        json={
            "item_name": "BOSCH GSB 185-LI 18V免碳刷震動電鑽",
            "original_image_url": "/test_assets/drill_checkin.jpg",
            "filename_hint": "drill_makita.jpg 牧田電鑽",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_swap.status_code == 200
    data_swap = res_swap.json()
    assert data_swap["is_same_object"] is False
    assert data_swap["requires_retake"] is True
    assert "調包" in data_swap["difference_notes"] or "品牌" in data_swap["difference_notes"]

    # 3. 現場取件拍攝同一實體物件 (Bosch 電鑽) ➔ 驗證通過！
    gw.rate_limits.clear()
    res_match = client.post(
        "/api/v1/items/verify-same-object",
        json={
            "item_name": "BOSCH GSB 185-LI 18V免碳刷震動電鑽",
            "original_image_url": "/test_assets/drill_checkin.jpg",
            "filename_hint": "drill_checkin.jpg",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_match.status_code == 200
    data_match = res_match.json()
    assert data_match["is_same_object"] is True
    assert data_match["requires_retake"] is False


def test_same_object_makita_vs_milwaukee_swap_prevention(client, setup_ai_env):
    """驗證原借 Makita 牧田電鑽，現場拍成 Milwaukee 美沃奇電鑽時，必須精準阻斷調包！"""
    token = setup_ai_env["token1"]
    gw = AIGateway.get_instance()
    gw.rate_limits.clear()

    res = client.post(
        "/api/v1/items/verify-same-object",
        json={
            "item_name": "Makita 牧田 DHP482 18V無刷充電式雙速震動電鑽",
            "original_image_url": "/test_assets/drill_makita.jpg",
            "filename_hint": "drill_milwaukee.jpg 美沃奇 M18 FUEL 衝擊電鑽",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_same_object"] is False
    assert data["requires_retake"] is True
    assert "調包" in data["difference_notes"] or "品牌" in data["difference_notes"]
    assert "Makita" in data["difference_notes"] or "牧田" in data["difference_notes"]


def test_ai_status_and_rag_ask_ai(client, setup_ai_env):
    """驗證 AI Gateway 狀態端點與知識庫 AI 增強問答端點"""
    # 1. 查詢 AI 連線狀態
    res_status = client.get("/api/v1/items/ai-status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "gemini" in status_data["model"]
    assert status_data["all_features_ai_driven"] is True
    assert "knowledge_base_ai" in status_data
    assert len(status_data["features"]) >= 4

    # 2. 測試知識庫 AI 即時問答端點
    res_qa = client.post(
        "/api/v1/rag/ask-ai",
        json={
            "question": "電鑽如果鑽水泥牆應該切換什麼模式？",
            "tool_id": "TOOL_DRILL_01",
        },
    )
    assert res_qa.status_code == 200
    qa_data = res_qa.json()
    assert "answer" in qa_data
    assert len(qa_data["answer"]) > 5
    assert "mascot_tip" in qa_data
    assert "狸利" in qa_data["mascot_tip"]




