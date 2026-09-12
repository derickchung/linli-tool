import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import User, Community, Item, Order, OrderStatus, VerificationStatus, ItemCategory


def test_cross_community_isolation_and_idor_protection(client: TestClient, db_session: Session):
    comm_a = Community(name="Community A", address="Address A")
    comm_b = Community(name="Community B", address="Address B")
    db_session.add_all([comm_a, comm_b])
    db_session.commit()

    from backend.services.auth_service import AuthService
    user_a1 = User(phone="0911111111", name="Resident A1", community_id=comm_a.id, verification_status=VerificationStatus.VALIDATED)
    user_b1 = User(phone="0922222222", name="Resident B1", community_id=comm_b.id, verification_status=VerificationStatus.VALIDATED)
    user_c = User(phone="0933333333", name="Outsider C", community_id=comm_a.id, verification_status=VerificationStatus.VALIDATED)
    db_session.add_all([user_a1, user_b1, user_c])
    db_session.commit()

    token_a1 = AuthService.create_access_token(user_a1.id, comm_a.id)
    token_b1 = AuthService.create_access_token(user_b1.id, comm_b.id)
    token_c = AuthService.create_access_token(user_c.id, comm_a.id)

    item_a = Item(
        owner_id=user_a1.id,
        community_id=comm_a.id,
        name="Community A Tool",
        category=ItemCategory.POWER_TOOLS,
        daily_rate=100,
        market_value=2000,
        damage_tool_id="tool-a",
    )
    db_session.add(item_a)
    db_session.commit()

    # 1. B1 tries to get A1 item detail -> 403 Forbidden
    res_get = client.get(f"/api/v1/items/{item_a.id}", headers={"Authorization": f"Bearer {token_b1}"})
    assert res_get.status_code == 403

    # 2. B1 tries to calculate fees for item A -> 403 Forbidden
    start = date.today() + timedelta(days=1)
    end = date.today() + timedelta(days=2)
    res_calc = client.post(
        "/api/v1/orders/calculate",
        json={"item_id": item_a.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_b1}"},
    )
    assert res_calc.status_code == 403

    # 3. B1 tries to order item A -> 403 Forbidden
    res_order = client.post(
        "/api/v1/orders/",
        json={"item_id": item_a.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_b1}"},
    )
    assert res_order.status_code == 403

    # 4. Outsider C (same community A) orders item A -> 201 Created
    res_order_ok = client.post(
        "/api/v1/orders/",
        json={"item_id": item_a.id, "start_date": str(start), "end_date": str(end)},
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert res_order_ok.status_code == 201
    order_id = res_order_ok.json()["id"]

    # 5. IDOR: B1 tries to view order detail -> 403 Forbidden
    res_order_view = client.get(f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {token_b1}"})
    assert res_order_view.status_code == 403

    # 6. IDOR: B1 tries to get handover code -> 403 Forbidden
    res_idor_code = client.get(f"/api/v1/orders/{order_id}/handover/code", headers={"Authorization": f"Bearer {token_b1}"})
    assert res_idor_code.status_code == 403

    # 7. IDOR: B1 tries to file dispute on order -> 403 Forbidden
    res_idor_dispute = client.post(
        "/api/v1/disputes/",
        json={"order_id": order_id, "reason": "Malicious dispute"},
        headers={"Authorization": f"Bearer {token_b1}"},
    )
    assert res_idor_dispute.status_code == 403


def test_sql_injection_and_xss_protection(client: TestClient, db_session: Session):
    comm = Community(name="Security Test Community", address="Sec Rd 1")
    db_session.add(comm)
    db_session.commit()

    from backend.services.auth_service import AuthService
    user = User(phone="0955555555", name="Security Tester", community_id=comm.id, verification_status=VerificationStatus.VALIDATED)
    db_session.add(user)
    db_session.commit()
    token = AuthService.create_access_token(user.id, comm.id)

    # 1. SQL Injection query
    sqli_query = "' OR '1'='1' --"
    res_search = client.get(f"/api/v1/items/?query={sqli_query}", headers={"Authorization": f"Bearer {token}"})
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 0

    # 2. XSS Tag injection
    xss_name = "<script>alert('xss')</script>"
    res_create = client.post(
        "/api/v1/items/",
        json={
            "name": xss_name,
            "category": "HAND_TOOLS",
            "daily_rate": 80,
            "market_value": 800,
            "accessories": ["<img src=x onerror=alert(1)>"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_create.status_code == 201
    item_id = res_create.json()["id"]

    res_get = client.get(f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_get.status_code == 200
    assert res_get.json()["name"] == xss_name

    # 3. Boundary validation
    today = date.today()
    res_bad_date = client.post(
        "/api/v1/orders/calculate",
        json={"item_id": item_id, "start_date": str(today + timedelta(days=5)), "end_date": str(today + timedelta(days=2))},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad_date.status_code == 422


def test_strict_forbidden_insurance_words_compliance():
    import os

    forbidden_terms = ["保險", "保費", "理賠金"]
    backend_dirs = ["backend/routers", "backend/services", "backend/models.py", "backend/schemas.py"]

    for target in backend_dirs:
        if os.path.isfile(target):
            files = [target]
        else:
            files = [os.path.join(target, f) for f in os.listdir(target) if f.endswith(".py")]

        for filepath in files:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                for idx, line in enumerate(lines, 1):
                    if "禁止" in line or "排除" in line or "Anti-pattern" in line or "forbidden" in line.lower() or "PRD" in line or "Spec" in line:
                        continue
                    for term in forbidden_terms:
                        assert term not in line, f'Found forbidden term "{term}" in {filepath}:{idx} -> {line}'
