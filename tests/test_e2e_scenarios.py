import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import User, Community, Item, Order, OrderStatus, VerificationStatus, ItemCategory
from backend.services.compensation_service import get_current_pool_balance


def test_scenario_1_clean_return_mainline(client: TestClient, db_session: Session):
    # Step 1: Register Lender and Create Community
    send_a = client.post('/api/v1/auth/otp/send', json={'phone': '0911001001'})
    otp_a = send_a.json()['mock_otp']
    res_verify_a = client.post('/api/v1/auth/otp/verify', json={'phone': '0911001001', 'otp': otp_a})
    assert res_verify_a.status_code == 200
    token_lender = res_verify_a.json()['access_token']
    lender_id = res_verify_a.json()['user']['id']

    # Lender creates Community (cold start makes creator VALIDATED)
    res_comm = client.post(
        '/api/v1/communities',
        json={'name': 'Community Sun Garden', 'address': 'Sun Garden Rd No.88'},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_comm.status_code == 201
    comm_id = res_comm.json()['id']

    # Step 2: Register Borrower and Join via Invitation
    send_b = client.post('/api/v1/auth/otp/send', json={'phone': '0922002002'})
    otp_b = send_b.json()['mock_otp']
    res_verify_b = client.post('/api/v1/auth/otp/verify', json={'phone': '0922002002', 'otp': otp_b})
    assert res_verify_b.status_code == 200
    token_renter = res_verify_b.json()['access_token']
    renter_id = res_verify_b.json()['user']['id']

    res_invite = client.post(
        f'/api/v1/communities/{comm_id}/invitations',
        json={'max_uses': 1},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_invite.status_code == 200
    invite_token = res_invite.json()['invitation_token']

    res_join = client.post(
        '/api/v1/communities/join',
        json={'token': invite_token},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_join.status_code == 200
    assert res_join.json()['status'] == 'VALIDATED'

    # Step 3: Item Listing & Browsing
    res_item = client.post(
        '/api/v1/items/',
        json={
            'name': 'Bosch 18V Hammer Drill',
            'category': 'POWER_TOOLS',
            'daily_rate': 150,
            'market_value': 4000,
            'damage_tool_id': 'drill-bosch-18v',
            'accessories': ['Battery 18V x2', 'Charger', 'Case'],
            'safety_tips': ['Wear eye goggles', 'Check pipes before drilling'],
        },
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_item.status_code == 201
    item_id = res_item.json()['id']

    res_list = client.get('/api/v1/items/', headers={'Authorization': f'Bearer {token_renter}'})
    assert res_list.status_code == 200
    assert any(it['id'] == item_id for it in res_list.json()['items'])

    # Step 4: Fee Calculation & Reservation
    start = date.today() + timedelta(days=2)
    end = date.today() + timedelta(days=4)
    res_calc = client.post(
        '/api/v1/orders/calculate',
        json={'item_id': item_id, 'start_date': str(start), 'end_date': str(end)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_calc.status_code == 200
    calc_info = res_calc.json()
    assert calc_info['rent_days'] == 3
    assert calc_info['total_rent'] == 450
    assert calc_info['base_deposit'] == 2250
    assert calc_info['deposit_discount_rate'] == 0.5
    assert calc_info['actual_deposit'] == 1125
    assert calc_info['authorized_total'] == 1575

    res_order = client.post(
        '/api/v1/orders/',
        json={'item_id': item_id, 'start_date': str(start), 'end_date': str(end)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_order.status_code == 201
    order_id = res_order.json()['id']
    assert res_order.json()['status'] == 'CONFIRMED'

    # Step 5: Handover Code Verification
    res_code = client.get(
        f'/api/v1/orders/{order_id}/handover/code',
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_code.status_code == 200
    handover_code = res_code.json()['handover_code']
    assert len(handover_code) == 6
    assert handover_code.isdigit()

    res_verify_handover = client.post(
        f'/api/v1/orders/{order_id}/handover/verify',
        json={'code': handover_code},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_verify_handover.status_code == 200
    assert res_verify_handover.json()['status'] == 'PICKED_UP'

    # Step 6: Check-in SHA-256 Photo
    checkin_img = 'https://storage.linli-tool.app/checkin/drill_fresh.jpg'
    res_checkin = client.post(
        f'/api/v1/orders/{order_id}/check-in',
        json={'image_url': checkin_img, 'notes': 'Good condition'},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_checkin.status_code == 200
    assert res_checkin.json()['status'] == 'IN_USE'
    assert len(res_checkin.json()['checksum_sha256']) == 64

    # Step 7: Check-out MATCH completion
    initial_balance, _, _ = get_current_pool_balance(db_session)

    res_checkout = client.post(
        f'/api/v1/orders/{order_id}/check-out',
        json={
            'image_url': 'https://storage.linli-tool.app/checkout/drill_clean.jpg',
            'notes': 'Normal dust, clean condition',
        },
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_checkout.status_code == 200
    checkout_data = res_checkout.json()
    assert checkout_data['status'] == 'COMPLETED'
    assert checkout_data['vision_evaluation']['result'] == 'MATCH'
    assert checkout_data['deposit_refunded'] == 1125
    assert checkout_data['credit_score_earned'] == 2

    # Verify credit score +2
    renter_user = db_session.query(User).filter(User.id == renter_id).first()
    lender_user = db_session.query(User).filter(User.id == lender_id).first()
    assert renter_user.credit_score == 82
    assert lender_user.credit_score == 82

    # Verify 15% platform fee into pool (450 * 0.15 = 68)
    final_balance, _, _ = get_current_pool_balance(db_session)
    assert final_balance == initial_balance + 68


def test_scenario_2_damage_and_pool_payout_dispute_mainline(client: TestClient, db_session: Session):
    # Step 1: Register Lender and Create Community
    send_l = client.post('/api/v1/auth/otp/send', json={'phone': '0933111222'})
    otp_l = send_l.json()['mock_otp']
    res_vl = client.post('/api/v1/auth/otp/verify', json={'phone': '0933111222', 'otp': otp_l})
    token_lender = res_vl.json()['access_token']
    lender_id = res_vl.json()['user']['id']

    res_comm = client.post(
        '/api/v1/communities',
        json={'name': 'Green Living Community', 'address': 'Green Rd No.100'},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_comm.status_code == 201
    comm_id = res_comm.json()['id']

    # Step 2: Register Borrower and Join
    send_r = client.post('/api/v1/auth/otp/send', json={'phone': '0944222333'})
    otp_r = send_r.json()['mock_otp']
    res_vr = client.post('/api/v1/auth/otp/verify', json={'phone': '0944222333', 'otp': otp_r})
    token_renter = res_vr.json()['access_token']
    renter_id = res_vr.json()['user']['id']

    res_inv = client.post(
        f'/api/v1/communities/{comm_id}/invitations',
        json={'max_uses': 1},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_inv.status_code == 200
    inv_token = res_inv.json()['invitation_token']

    res_join = client.post(
        '/api/v1/communities/join',
        json={'token': inv_token},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_join.status_code == 200
    assert res_join.json()['status'] == 'VALIDATED'

    # Step 3: List Washer (Demo tool)
    res_item = client.post(
        '/api/v1/items/',
        json={
            'name': 'Karcher K4 Pressure Washer',
            'category': 'CLEANING',
            'daily_rate': 300,
            'market_value': 6000,
            'damage_tool_id': 'washer-karcher-k4',
            'accessories': ['Hose 10m', 'Spray Gun', 'Nozzle'],
        },
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_item.status_code == 201
    item_id = res_item.json()['id']

    # Step 4: Book 2 days (rent 600, deposit 2250)
    start = date.today() + timedelta(days=1)
    end = date.today() + timedelta(days=2)
    res_order = client.post(
        '/api/v1/orders/',
        json={'item_id': item_id, 'start_date': str(start), 'end_date': str(end)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_order.status_code == 201
    order_id = res_order.json()['id']

    # Step 5: Handover & Check-in
    res_code = client.get(
        f'/api/v1/orders/{order_id}/handover/code',
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_code.status_code == 200
    code = res_code.json()['handover_code']

    res_verify = client.post(
        f'/api/v1/orders/{order_id}/handover/verify',
        json={'code': code},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_verify.status_code == 200

    res_checkin = client.post(
        f'/api/v1/orders/{order_id}/check-in',
        json={'image_url': 'https://storage.linli-tool.app/checkin/washer_clean.jpg'},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_checkin.status_code == 200

    # Step 6: Return Check-out with Damage keyword
    res_checkout = client.post(
        f'/api/v1/orders/{order_id}/check-out',
        json={
            'image_url': 'https://storage.linli-tool.app/checkout/washer_broken_gun.jpg',
            'notes': 'damage: spray gun shell cracked and broken',
        },
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_checkout.status_code == 200
    checkout_data = res_checkout.json()
    assert checkout_data['status'] == 'INSPECTION'
    assert checkout_data['vision_evaluation']['result'] == 'DAMAGE_DETECTED'

    # Verify residual and pool payout in DB
    order_in_db = db_session.query(Order).filter(Order.id == order_id).first()
    assert order_in_db.compensation_amount == 4200
    assert order_in_db.pool_payout == 1950

    # Step 7: Dispute Ticket Workflow
    res_dispute = client.post(
        '/api/v1/disputes/',
        json={
            'order_id': order_id,
            'reason': 'Small hairline crack already present at pickup time.',
            'evidence_images': ['https://evidence.linli-tool.app/disputes/washer_crack_detail.jpg'],
        },
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_dispute.status_code == 201
    dispute_id = res_dispute.json()['id']
    assert res_dispute.json()['status'] == 'OPEN'

    # Funds frozen & status DISPUTED
    db_session.refresh(order_in_db)
    assert order_in_db.status == OrderStatus.DISPUTED

    # Both parties can query
    res_get_disp = client.get(
        f'/api/v1/disputes/{dispute_id}',
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_get_disp.status_code == 200
    assert 'Small hairline crack' in res_get_disp.json()['reason']

    # Admin/Management resolves dispute
    res_resolve = client.patch(
        f'/api/v1/disputes/{dispute_id}/resolve',
        json={
            'status': 'RESOLVED',
            'resolution_notes': 'Reviewed pickup video, verified pre-existing fatigue crack. Pool subsidizes and deposit released.',
        },
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()['status'] == 'RESOLVED'


def test_scenario_3_custom_tool_damage_option_b_fallback(client: TestClient, db_session: Session):
    # Step 1: Setup community and users
    send_l = client.post('/api/v1/auth/otp/send', json={'phone': '0955111222'})
    otp_l = send_l.json()['mock_otp']
    res_vl = client.post('/api/v1/auth/otp/verify', json={'phone': '0955111222', 'otp': otp_l})
    token_lender = res_vl.json()['access_token']

    res_comm = client.post(
        '/api/v1/communities',
        json={'name': 'Custom Tool Community', 'address': 'Custom Rd 1'},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    comm_id = res_comm.json()['id']

    send_r = client.post('/api/v1/auth/otp/send', json={'phone': '0966222333'})
    otp_r = send_r.json()['mock_otp']
    res_vr = client.post('/api/v1/auth/otp/verify', json={'phone': '0966222333', 'otp': otp_r})
    token_renter = res_vr.json()['access_token']

    res_inv = client.post(
        f'/api/v1/communities/{comm_id}/invitations',
        json={'max_uses': 1},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    inv_token = res_inv.json()['invitation_token']
    client.post('/api/v1/communities/join', json={'token': inv_token}, headers={'Authorization': f'Bearer {token_renter}'})

    # Step 2: List a non-demo custom tool (damage_tool_id = None)
    res_item = client.post(
        '/api/v1/items/',
        json={
            'name': 'DIY Custom Woodworking Jigsaw',
            'category': 'POWER_TOOLS',
            'daily_rate': 80,
            'market_value': 1200,
            'damage_tool_id': None,
        },
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    assert res_item.status_code == 201
    item_id = res_item.json()['id']

    # Step 3: Book tool (rent 160, deposit = 80 * 15 * 0.5 = 600)
    start = date.today() + timedelta(days=3)
    end = date.today() + timedelta(days=4)
    res_order = client.post(
        '/api/v1/orders/',
        json={'item_id': item_id, 'start_date': str(start), 'end_date': str(end)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_order.status_code == 201
    order_id = res_order.json()['id']

    # Step 4: Handover & Check-in
    res_code = client.get(f'/api/v1/orders/{order_id}/handover/code', headers={'Authorization': f'Bearer {token_renter}'})
    code = res_code.json()['handover_code']
    client.post(f'/api/v1/orders/{order_id}/handover/verify', json={'code': code}, headers={'Authorization': f'Bearer {token_lender}'})
    client.post(f'/api/v1/orders/{order_id}/check-in', json={'image_url': 'https://storage.linli-tool.app/checkin/saw.jpg'}, headers={'Authorization': f'Bearer {token_renter}'})

    # Step 5: Check-out DAMAGE_DETECTED
    res_checkout = client.post(
        f'/api/v1/orders/{order_id}/check-out',
        json={
            'image_url': 'https://storage.linli-tool.app/checkout/saw_broken.jpg',
            'notes': 'damage: motor burned and blade guide broken',
        },
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    assert res_checkout.status_code == 200
    assert res_checkout.json()['status'] == 'INSPECTION'

    # Step 6: Verify Option B Fallback (Pure deposit forfeiture, 0 pool payout)
    order_in_db = db_session.query(Order).filter(Order.id == order_id).first()
    assert order_in_db.compensation_amount == 840
    assert order_in_db.pool_payout == 0


def test_scenario_4_cancellation_refund_thresholds(client: TestClient, db_session: Session):
    # Setup
    send_l = client.post('/api/v1/auth/otp/send', json={'phone': '0977111222'})
    otp_l = send_l.json()['mock_otp']
    res_vl = client.post('/api/v1/auth/otp/verify', json={'phone': '0977111222', 'otp': otp_l})
    token_lender = res_vl.json()['access_token']

    res_comm = client.post(
        '/api/v1/communities',
        json={'name': 'Cancellation Policy Community', 'address': 'Cancel Rd 1'},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    comm_id = res_comm.json()['id']

    send_r = client.post('/api/v1/auth/otp/send', json={'phone': '0988222333'})
    otp_r = send_r.json()['mock_otp']
    res_vr = client.post('/api/v1/auth/otp/verify', json={'phone': '0988222333', 'otp': otp_r})
    token_renter = res_vr.json()['access_token']

    res_inv = client.post(f'/api/v1/communities/{comm_id}/invitations', json={'max_uses': 1}, headers={'Authorization': f'Bearer {token_lender}'})
    inv_token = res_inv.json()['invitation_token']
    client.post('/api/v1/communities/join', json={'token': inv_token}, headers={'Authorization': f'Bearer {token_renter}'})

    # List tool: daily_rate 200, deposit 1500
    res_item = client.post(
        '/api/v1/items/',
        json={'name': 'Heavy Duty Ladder', 'category': 'HAND_TOOLS', 'daily_rate': 200, 'market_value': 3000},
        headers={'Authorization': f'Bearer {token_lender}'},
    )
    item_id = res_item.json()['id']

    # Case 1: Order starting in 5 days (> 24 hours) -> Free Cancellation
    start_far = date.today() + timedelta(days=5)
    end_far = date.today() + timedelta(days=6)
    res_order1 = client.post(
        '/api/v1/orders/',
        json={'item_id': item_id, 'start_date': str(start_far), 'end_date': str(end_far)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    order1_id = res_order1.json()['id']

    res_cancel1 = client.post(f'/api/v1/orders/{order1_id}/cancel', headers={'Authorization': f'Bearer {token_renter}'})
    assert res_cancel1.status_code == 200
    c_data1 = res_cancel1.json()
    assert c_data1['cancellation_fee'] == 0
    assert c_data1['refund_rent'] == 400
    assert c_data1['refund_deposit'] == 1500
    assert '滿 24 小時' in c_data1['message']

    # Case 2: Order starting today (< 24 hours) -> 20% Fee Cancellation
    start_near = date.today()
    end_near = date.today() + timedelta(days=1)
    res_order2 = client.post(
        '/api/v1/orders/',
        json={'item_id': item_id, 'start_date': str(start_near), 'end_date': str(end_near)},
        headers={'Authorization': f'Bearer {token_renter}'},
    )
    order2_id = res_order2.json()['id']

    res_cancel2 = client.post(f'/api/v1/orders/{order2_id}/cancel', headers={'Authorization': f'Bearer {token_renter}'})
    assert res_cancel2.status_code == 200
    c_data2 = res_cancel2.json()
    assert c_data2['cancellation_fee'] == 80
    assert c_data2['refund_rent'] == 320
    assert c_data2['refund_deposit'] == 1500
    assert '20% 租金手續費' in c_data2['message']
