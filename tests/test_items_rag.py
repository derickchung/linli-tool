import time
import pytest
from datetime import date
from backend.models import Community, VerificationStatus, Order, OrderStatus, ItemStatus


@pytest.fixture
def setup_community_and_users(db_session, create_test_user):
    # Create Community 1
    c1 = Community(name="國泰四季社區", address="台北市信義區忠孝東路五段100號")
    # Create Community 2
    c2 = Community(name="遠雄左岸社區", address="新北市中和區中原街50號")
    db_session.add_all([c1, c2])
    db_session.commit()
    db_session.refresh(c1)
    db_session.refresh(c2)

    # Validated User in Community 1
    u1, token1 = create_test_user(
        phone="0911000001",
        name="Alex (國泰)",
        status=VerificationStatus.VALIDATED,
        community_id=c1.id,
    )
    # Another Validated User in Community 1
    u1_neighbor, token1_neighbor = create_test_user(
        phone="0911000002",
        name="Bob (國泰鄰居)",
        status=VerificationStatus.VALIDATED,
        community_id=c1.id,
    )
    # Validated User in Community 2
    u2, token2 = create_test_user(
        phone="0922000001",
        name="David (遠雄)",
        status=VerificationStatus.VALIDATED,
        community_id=c2.id,
    )
    # Pending User in Community 1
    u_pending, token_pending = create_test_user(
        phone="0933000001",
        name="Pending住戶",
        status=VerificationStatus.PENDING,
        community_id=c1.id,
    )

    return {
        "c1": c1,
        "c2": c2,
        "u1": u1,
        "token1": token1,
        "u1_neighbor": u1_neighbor,
        "token1_neighbor": token1_neighbor,
        "u2": u2,
        "token2": token2,
        "u_pending": u_pending,
        "token_pending": token_pending,
    }


# ==========================================
# Task 2.1: Tool CRUD & Community Isolation
# ==========================================

def test_create_item_success(client, setup_community_and_users):
    token = setup_community_and_users["token1"]
    payload = {
        "name": "Bosch 12V 雙速衝擊電鑽",
        "category": "POWER_TOOLS",
        "daily_rate": 150,
        "market_value": 3200,
        "damage_tool_id": "TOOL_DRILL_01",
        "accessories": ["主機", "鋰電池x2", "座充充電器", "手提盒"],
        "safety_notes": "請務必配戴護目鏡與手套，避開暗埋管線。",
        "image_url": "https://example.com/drill.jpg",
    }
    response = client.post(
        "/api/v1/items/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bosch 12V 雙速衝擊電鑽"
    assert data["category"] == "POWER_TOOLS"
    assert data["daily_rate"] == 150
    assert data["market_value"] == 3200
    assert data["damage_tool_id"] == "TOOL_DRILL_01"
    assert len(data["accessories"]) == 4
    assert data["status"] == "AVAILABLE"
    assert data["community_id"] == setup_community_and_users["c1"].id
    assert data["owner_name"] == "Alex (國泰)"


def test_create_item_validation_and_permissions(client, setup_community_and_users):
    token1 = setup_community_and_users["token1"]
    token_pending = setup_community_and_users["token_pending"]

    # 1. Pending user cannot create item
    res_pending = client.post(
        "/api/v1/items/",
        json={
            "name": "普通扳手",
            "category": "HAND_TOOLS",
            "daily_rate": 50,
            "market_value": 500,
        },
        headers={"Authorization": f"Bearer {token_pending}"},
    )
    assert res_pending.status_code == 403
    assert "驗證" in res_pending.json()["detail"]

    # 2. Market value out of range (spec: 100 ~ 100,000)
    res_low = client.post(
        "/api/v1/items/",
        json={
            "name": "螺絲起子",
            "category": "HAND_TOOLS",
            "daily_rate": 10,
            "market_value": 50,  # Below 100
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_low.status_code == 422

    res_high = client.post(
        "/api/v1/items/",
        json={
            "name": "重型怪手",
            "category": "POWER_TOOLS",
            "daily_rate": 5000,
            "market_value": 200000,  # Above 100,000
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_high.status_code == 422


def test_community_multi_tenant_isolation(client, setup_community_and_users):
    token1 = setup_community_and_users["token1"]
    token2 = setup_community_and_users["token2"]

    # User 1 in Community 1 creates Drill
    res1 = client.post(
        "/api/v1/items/",
        json={
            "name": "國泰社區衝擊電鑽",
            "category": "POWER_TOOLS",
            "daily_rate": 120,
            "market_value": 2500,
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res1.status_code == 201
    item1_id = res1.json()["id"]

    # User 2 in Community 2 creates Washer
    res2 = client.post(
        "/api/v1/items/",
        json={
            "name": "遠雄社區高壓清洗機",
            "category": "CLEANING",
            "daily_rate": 200,
            "market_value": 4500,
        },
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res2.status_code == 201
    item2_id = res2.json()["id"]

    # User 1 lists items -> sees only Community 1's items
    list1 = client.get("/api/v1/items/", headers={"Authorization": f"Bearer {token1}"})
    assert list1.status_code == 200
    items1 = list1.json()["items"]
    assert any(i["id"] == item1_id for i in items1)
    assert not any(i["id"] == item2_id for i in items1)

    # User 2 lists items -> sees only Community 2's items
    list2 = client.get("/api/v1/items/", headers={"Authorization": f"Bearer {token2}"})
    assert list2.status_code == 200
    items2 = list2.json()["items"]
    assert any(i["id"] == item2_id for i in items2)
    assert not any(i["id"] == item1_id for i in items2)

    # User 1 attempts to view Community 2's item detail directly -> 403 Forbidden
    res_cross = client.get(
        f"/api/v1/items/{item2_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_cross.status_code == 403
    assert "跨社區資料隔離保護" in res_cross.json()["detail"]


def test_update_item_status_and_info(client, setup_community_and_users):
    token1 = setup_community_and_users["token1"]
    token1_neighbor = setup_community_and_users["token1_neighbor"]

    # Create item
    res = client.post(
        "/api/v1/items/",
        json={
            "name": "伸縮鋁梯",
            "category": "HAND_TOOLS",
            "daily_rate": 80,
            "market_value": 1800,
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    item_id = res.json()["id"]

    # Neighbor attempts to change status -> 403 Forbidden
    res_forbidden = client.patch(
        f"/api/v1/items/{item_id}/status",
        json={"status": "MAINTENANCE"},
        headers={"Authorization": f"Bearer {token1_neighbor}"},
    )
    assert res_forbidden.status_code == 403

    # Owner changes status to MAINTENANCE
    res_owner = client.patch(
        f"/api/v1/items/{item_id}/status",
        json={"status": "MAINTENANCE"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_owner.status_code == 200
    assert res_owner.json()["status"] == "MAINTENANCE"

    # Owner updates tool rate and name
    res_update = client.put(
        f"/api/v1/items/{item_id}",
        json={"name": "升級款伸縮鋁梯 (附平衡桿)", "daily_rate": 100},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "升級款伸縮鋁梯 (附平衡桿)"
    assert res_update.json()["daily_rate"] == 100


# ==========================================
# Task 2.2: Local RAG FAQ Retrieval (U1)
# ==========================================

def test_local_rag_faq_latency_and_accuracy(client):
    # Warm up client and route initialization to eliminate first-call cold-start jitter
    client.post("/api/v1/rag/faq", json={"tool_id": "TOOL_DRILL_01", "question": "暖機測試"})

    test_queries = [
        ("TOOL_DRILL_01", "如何在磚牆上更換鑽尾？", "夾頭"),
        ("TOOL_WASHER_01", "如何排空空氣防馬達燒毀？", "水龍頭"),
        ("TOOL_LADDER_01", "如何安全收攏伸縮梯？", "夾手"),
        ("TOOL_VACUUM_01", "吸水跟吸灰塵怎麼更換濾網？", "HEPA"),
        ("TOOL_LASER_01", "一直發出嗶嗶嗶警報聲怎麼辦？", "安平"),
    ]

    for tool_id, question, expected_keyword in test_queries:
        start_time = time.perf_counter()
        response = client.post(
            "/api/v1/rag/faq",
            json={"tool_id": tool_id, "question": question},
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Performance requirement: latency < 50ms
        assert elapsed_ms < 50.0, f"Query '{question}' took {elapsed_ms:.2f}ms (> 50ms)"
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] > 0.3
        assert expected_keyword in data["answer"]
        assert "knowledge_base" in data["source"]


def test_local_rag_faq_fallback(client):
    # Irrelevant / unsupported question
    response = client.post(
        "/api/v1/rag/faq",
        json={"question": "明天台北天氣會下雨嗎？有政治八卦嗎？"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["confidence"] == 0.0
    assert "狸利" in data["answer"]
    assert "fallback" in data["source"]


# ==========================================
# Task 2.3: UC-4 Safety Alerts by Category
# ==========================================

def test_safety_alert_categories(client):
    # Power tools: High risk
    res_power = client.get("/api/v1/rag/safety/POWER_TOOLS")
    assert res_power.status_code == 200
    data_power = res_power.json()
    assert data_power["risk_level"] == "HIGH"
    assert any("護目鏡" in ppe for ppe in data_power["required_ppe"])
    assert any("口罩" in ppe for ppe in data_power["required_ppe"])
    assert "狸利" in data_power["microcopy_tip"]

    # Cleaning: Medium risk
    res_clean = client.get("/api/v1/rag/safety/CLEANING")
    assert res_clean.status_code == 200
    assert res_clean.json()["risk_level"] == "MEDIUM"

    # Hand tools: Low risk
    res_hand = client.get("/api/v1/rag/safety/HAND_TOOLS")
    assert res_hand.status_code == 200
    assert res_hand.json()["risk_level"] == "LOW"


# ==========================================
# Task 2.4: UC-5 Equipment Health Engine
# ==========================================

def test_equipment_health_calculation(client, db_session, setup_community_and_users):
    token1 = setup_community_and_users["token1"]
    u1 = setup_community_and_users["u1"]
    u1_neighbor = setup_community_and_users["u1_neighbor"]

    # Create Item
    res_item = client.post(
        "/api/v1/items/",
        json={
            "name": "Karcher 高壓清洗機",
            "category": "CLEANING",
            "daily_rate": 200,
            "market_value": 4500,
            "damage_tool_id": "TOOL_WASHER_01",
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    item_id = res_item.json()["id"]

    # Scenario 1: New tool with 0 rentals -> Grade A
    res_health_a1 = client.get(
        f"/api/v1/items/{item_id}/health",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_health_a1.status_code == 200
    data_a1 = res_health_a1.json()
    assert data_a1["health_grade"] == "A"
    assert data_a1["total_rentals"] == 0
    assert data_a1["damage_count"] == 0

    # Scenario 2: Add 5 completed orders with MATCH (no damage) -> Grade A
    for i in range(5):
        order = Order(
            order_no=f"ORD_M_{i}",
            item_id=item_id,
            renter_id=u1_neighbor.id,
            lender_id=u1.id,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            rent_days=2,
            daily_rate=200,
            total_rent=400,
            base_deposit=3000,
            actual_deposit=0,
            status=OrderStatus.COMPLETED,
            vision_result="MATCH",
        )
        db_session.add(order)
    db_session.commit()

    res_health_a2 = client.get(
        f"/api/v1/items/{item_id}/health",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data_a2 = res_health_a2.json()
    assert data_a2["health_grade"] == "A"
    assert data_a2["total_rentals"] == 5
    assert data_a2["damage_count"] == 0

    # Scenario 3: Add 5 more orders (total 10 rentals), with 1 MINOR_DIFF damage event (1/10 = 10% <= 15%) -> Grade B
    order_diff = Order(
        order_no="ORD_DIFF_1",
        item_id=item_id,
        renter_id=u1_neighbor.id,
        lender_id=u1.id,
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
        rent_days=2,
        daily_rate=200,
        total_rent=400,
        base_deposit=3000,
        actual_deposit=0,
        status=OrderStatus.COMPLETED,
        vision_result="MINOR_DIFF",
    )
    db_session.add(order_diff)
    for i in range(4):
        db_session.add(
            Order(
                order_no=f"ORD_M2_{i}",
                item_id=item_id,
                renter_id=u1_neighbor.id,
                lender_id=u1.id,
                start_date=date(2026, 9, 5),
                end_date=date(2026, 9, 6),
                rent_days=2,
                daily_rate=200,
                total_rent=400,
                base_deposit=3000,
                actual_deposit=0,
                status=OrderStatus.COMPLETED,
                vision_result="MATCH",
            )
        )
    db_session.commit()

    res_health_b = client.get(
        f"/api/v1/items/{item_id}/health",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data_b = res_health_b.json()
    assert data_b["health_grade"] == "B"
    assert data_b["total_rentals"] == 10
    assert data_b["damage_count"] == 1
    assert data_b["damage_rate"] == 0.1

    # Scenario 4: Add another DAMAGE_DETECTED event without increasing completed rentals proportionally (e.g. 2/10 = 20% > 15%) -> Grade C
    order_damage = Order(
        order_no="ORD_DAM_2",
        item_id=item_id,
        renter_id=u1_neighbor.id,
        lender_id=u1.id,
        start_date=date(2026, 9, 7),
        end_date=date(2026, 9, 8),
        rent_days=2,
        daily_rate=200,
        total_rent=400,
        base_deposit=3000,
        actual_deposit=0,
        status=OrderStatus.COMPLETED,
        vision_result="DAMAGE_DETECTED",
    )
    db_session.add(order_damage)
    db_session.commit()

    res_health_c = client.get(
        f"/api/v1/items/{item_id}/health",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data_c = res_health_c.json()
    assert data_c["health_grade"] == "C"
    assert data_c["damage_count"] == 2
    assert data_c["damage_rate"] > 0.15
    assert "Ghost Overlay" in data_c["maintenance_advice"]


def test_json_knowledge_base_and_rag_endpoints(client):
    from backend.services.rag_local_service import LocalKnowledgeBase

    kb = LocalKnowledgeBase.get_instance()
    assert len(kb.json_chunks) >= 30
    assert len(kb.scenario_chunks) >= 5

    # 1. Test A2 find_tool_by_scenario
    drill_matches = kb.find_tool_by_scenario("我想在客廳水泥牆釘層板掛畫")
    assert len(drill_matches) >= 1
    assert "bosch" in drill_matches[0]["tool_id"]
    assert any("釘層板" in t or "掛畫" in t for t in drill_matches[0]["matched_tags"])

    # 2. Test A2 scenario endpoint
    res_scen = client.post(
        "/api/v1/rag/scenario-tools",
        json={"prompt": "浴室洗陽台想要去水垢"},
    )
    assert res_scen.status_code == 200
    scen_data = res_scen.json()
    assert len(scen_data) >= 1
    assert any("karcher" in m["tool_id"] or "清洗機" in m["tool_name"] for m in scen_data)

    # 3. Test SPEC_04 damage-criteria endpoint (canonical ID & alias)
    res_crit_canon = client.get("/api/v1/rag/damage-criteria/bosch-gsb185li-30pc")
    assert res_crit_canon.status_code == 200
    crit_data = res_crit_canon.json()
    assert "30%" in crit_data["minor_diff_criteria"]
    assert "100%" in crit_data["damage_detected_criteria"]
    assert "馬達" in crit_data["excluded_scope"] or "功能性" in crit_data["excluded_scope"]

    res_crit_alias = client.get("/api/v1/rag/damage-criteria/TOOL_DRILL_01")
    assert res_crit_alias.status_code == 200
    assert res_crit_alias.json()["tool_id"] == "bosch-gsb185li-30pc"

    # 4. Test U1 tool-content endpoint
    res_content = client.get("/api/v1/rag/tool-content/bosch-gsb185li-30pc?category=操作手冊")
    assert res_content.status_code == 200
    content_data = res_content.json()
    assert len(content_data) >= 1
    assert "扭力" in content_data[0]["content"] or "鑽孔" in content_data[0]["content"]
    assert "[official_manual]" in content_data[0]["source_ref"]

