import time
import base64
import json
import hmac
import hashlib
from datetime import datetime, timedelta

from backend.models import User, VerificationStatus
from backend.services.auth_service import AuthService, HMAC_SECRET


def test_create_community_cold_start(client, create_test_user):
    user, token = create_test_user(phone="0911000111", status=VerificationStatus.PENDING)

    response = client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "國泰四季大樓", "address": "台北市大安區和平東路二段100號"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "國泰四季大樓"
    assert data["member_count"] == 1
    community_id = data["id"]

    # Creator should now be VALIDATED and linked to community
    me_res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["verification_status"] == VerificationStatus.VALIDATED.value
    assert me_data["community_id"] == community_id


def test_create_duplicate_community(client, create_test_user):
    user, token = create_test_user(phone="0911000222")

    # Create first
    client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "仁愛名廬", "address": "台北市大安區仁愛路四段50號"},
    )

    # Attempt to create duplicate
    dup_res = client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "仁愛名廬", "address": "台北市大安區仁愛路四段50號"},
    )
    assert dup_res.status_code == 409
    assert "已存在" in dup_res.json()["detail"]


def test_generate_invitation_token(client, create_test_user):
    # Validated user in community 1
    user1, token1 = create_test_user(
        phone="0911000333", status=VerificationStatus.VALIDATED, community_id=1
    )

    # First ensure community 1 exists
    client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {token1}"},
        json={"name": "富邦天母社區", "address": "台北市士林區天母西路20號"},
    )
    # Refresh token to get assigned community_id
    token1 = AuthService.create_access_token(user1.id, user1.community_id)

    # Generate invitation
    inv_res = client.post(
        f"/api/v1/communities/{user1.community_id}/invitations",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert inv_res.status_code == 200
    data = inv_res.json()
    assert "invitation_token" in data
    assert "share_url" in data
    assert "." in data["invitation_token"]


def test_non_validated_user_cannot_generate_invitation(client, create_test_user):
    user, token = create_test_user(phone="0911000444", status=VerificationStatus.PENDING)

    inv_res = client.post(
        "/api/v1/communities/1/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert inv_res.status_code == 403
    assert "尚未通過社區住戶驗證" in inv_res.json()["detail"]


def test_join_community_success(client, create_test_user):
    # 1. User A creates community and is VALIDATED
    userA, tokenA = create_test_user(phone="0911000555", name="住戶大衛")
    com_res = client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {tokenA}"},
        json={"name": "信義之星", "address": "台北市信義區松智路1號"},
    )
    community_id = com_res.json()["id"]
    tokenA = AuthService.create_access_token(userA.id, community_id)

    # 2. User A issues invitation
    inv_res = client.post(
        f"/api/v1/communities/{community_id}/invitations",
        headers={"Authorization": f"Bearer {tokenA}"},
    )
    inv_token = inv_res.json()["invitation_token"]

    # 3. User B joins via invitation
    userB, tokenB = create_test_user(phone="0911000666", name="住戶艾力克斯")
    join_res = client.post(
        "/api/v1/communities/join",
        headers={"Authorization": f"Bearer {tokenB}"},
        json={"token": inv_token},
    )
    assert join_res.status_code == 200
    join_data = join_res.json()
    assert join_data["success"] is True
    assert join_data["status"] == VerificationStatus.VALIDATED.value
    assert "信義之星" in join_data["community_name"]

    # Verify User B profile
    me_res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokenB}"})
    assert me_res.json()["verification_status"] == VerificationStatus.VALIDATED.value
    assert me_res.json()["community_id"] == community_id


def test_join_community_tampered_token(client, create_test_user):
    userA, tokenA = create_test_user(phone="0911000777")
    com_res = client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {tokenA}"},
        json={"name": "遠雄中央公園", "address": "新北市新莊區中央路1號"},
    )
    community_id = com_res.json()["id"]
    tokenA = AuthService.create_access_token(userA.id, community_id)

    inv_res = client.post(
        f"/api/v1/communities/{community_id}/invitations",
        headers={"Authorization": f"Bearer {tokenA}"},
    )
    inv_token = inv_res.json()["invitation_token"]

    # Tamper with the token
    tampered = inv_token[:-4] + "ffff"

    userB, tokenB = create_test_user(phone="0911000888")
    join_res = client.post(
        "/api/v1/communities/join",
        headers={"Authorization": f"Bearer {tokenB}"},
        json={"token": tampered},
    )
    assert join_res.status_code == 403
    assert "簽章無效" in join_res.json()["detail"]


def test_join_community_expired_token(client, create_test_user):
    user, token = create_test_user(phone="0911000999")

    # Manually create an expired token
    expired_payload = {
        "inviter_id": 1,
        "community_id": 1,
        "exp": int(time.time()) - 3600,  # 1 hour ago
    }
    payload_bytes = json.dumps(expired_payload, sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(
        HMAC_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    expired_token = f"{payload_b64}.{signature}"

    join_res = client.post(
        "/api/v1/communities/join",
        headers={"Authorization": f"Bearer {token}"},
        json={"token": expired_token},
    )
    assert join_res.status_code == 400
    assert "已過期" in join_res.json()["detail"]
