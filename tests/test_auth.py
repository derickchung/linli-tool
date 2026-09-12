from backend.models import User, VerificationStatus


def test_send_otp_success(client):
    response = client.post("/api/v1/auth/otp/send", json={"phone": "0912345678"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["expires_in"] == 180
    assert len(data["mock_otp"]) == 6


def test_send_otp_invalid_phone(client):
    response = client.post("/api/v1/auth/otp/send", json={"phone": "12345"})
    assert response.status_code == 422


def test_send_otp_rate_limit(client):
    phone = "0988776655"
    for _ in range(5):
        res = client.post("/api/v1/auth/otp/send", json={"phone": phone})
        assert res.status_code == 200

    # 6th attempt should be rejected with 429
    res = client.post("/api/v1/auth/otp/send", json={"phone": phone})
    assert res.status_code == 429
    assert "上限" in res.json()["detail"]


def test_verify_otp_success_creates_user(client):
    phone = "0922334455"
    send_res = client.post("/api/v1/auth/otp/send", json={"phone": phone})
    otp = send_res.json()["mock_otp"]

    verify_res = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["phone"] == phone
    assert data["user"]["credit_score"] == 80
    assert data["user"]["verification_status"] == VerificationStatus.PENDING.value


def test_verify_otp_wrong_code_and_attempts_limit(client):
    phone = "0933445566"
    client.post("/api/v1/auth/otp/send", json={"phone": phone})

    # 1st wrong try
    res1 = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
    assert res1.status_code == 400
    assert "剩餘嘗試次數：2" in res1.json()["detail"]

    # 2nd wrong try
    res2 = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
    assert res2.status_code == 400
    assert "剩餘嘗試次數：1" in res2.json()["detail"]

    # 3rd wrong try -> invalidated
    res3 = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": "000000"})
    assert res3.status_code == 400
    assert "已強制失效" in res3.json()["detail"]


def test_get_current_user_profile(client, create_test_user):
    user, token = create_test_user(phone="0955667788", name="Alex")

    # Unauthorized without token
    unauth_res = client.get("/api/v1/users/me")
    assert unauth_res.status_code == 401

    # Authorized with token
    auth_res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert auth_res.status_code == 200
    data = auth_res.json()
    assert data["id"] == user.id
    assert data["name"] == "Alex"
    assert data["phone"] == "0955667788"


def test_update_user_profile(client, create_test_user):
    user, token = create_test_user(phone="0966778899", name="舊名稱")

    res = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "新鄰居 Alex"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "新鄰居 Alex"
