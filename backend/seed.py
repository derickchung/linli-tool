"""
Database seed utility for LinLi Tool.
Ensures essential community, users, inventory tools, and active test orders exist.
"""
import json
from datetime import date, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Community, User, Item, Order, CompensationLedger, VerificationStatus, ItemCategory, ItemStatus, OrderStatus

def seed_initial_data():
    db: Session = SessionLocal()
    try:
        # 1. Ensure Community 1
        comm = db.query(Community).filter(Community.id == 1).first()
        if not comm:
            comm = Community(
                id=1,
                name="新店陽光花園社區",
                address="新北市新店區陽光路100號"
            )
            db.add(comm)
            db.commit()
            db.refresh(comm)

        # 2. Ensure Users
        user_chen = db.query(User).filter(User.id == 101).first()
        if not user_chen:
            user_chen = User(
                id=101,
                phone="0911000101",
                name="出借人老陳",
                community_id=1,
                verification_status=VerificationStatus.VALIDATED,
                credit_score=96
            )
            db.add(user_chen)

        user_lin = db.query(User).filter(User.id == 102).first()
        if not user_lin:
            user_lin = User(
                id=102,
                phone="0922000102",
                name="借用人小琳",
                community_id=1,
                verification_status=VerificationStatus.VALIDATED,
                credit_score=90
            )
            db.add(user_lin)
        db.commit()

        # 3. Ensure 5 Standard Tools (Aligned with knowledge_base.json)
        standard_items = [
            {
                "id": 1,
                "owner_id": 101,
                "community_id": 1,
                "name": "BOSCH GSB 185-LI 18V免碳刷震動電鑽+30件鍍鈦鑽頭組",
                "category": ItemCategory.POWER_TOOLS,
                "daily_rate": 150,
                "market_value": 3500,
                "damage_tool_id": "bosch-gsb185li-30pc",
                "status": ItemStatus.AVAILABLE,
                "accessories": ["電鑽主機", "18V 2.0Ah鋰電池", "原廠充電座", "30件鍍鈦鑽頭組", "手提工具箱"],
                "safety_notes": "水泥牆鑽孔請務必佩戴護目鏡，鑽孔前請以探測器確認暗埋管線。",
                "image_url": "/test_assets/drill_checkin.jpg",
            },
            {
                "id": 2,
                "owner_id": 101,
                "community_id": 1,
                "name": "Kärcher K 3 Power Control 高壓清洗機",
                "category": ItemCategory.CLEANING,
                "daily_rate": 250,
                "market_value": 5800,
                "damage_tool_id": "karcher-k3-power-control",
                "status": ItemStatus.AVAILABLE,
                "accessories": ["高壓噴槍 G 120 Q", "Vario Power 噴桿", "螺旋噴桿", "自吸水管"],
                "safety_notes": "高壓水柱衝擊力強，嚴禁對準人體或寵物。開機前務必先開水龍頭排空管內空氣。",
                "image_url": "https://images.unsplash.com/photo-1581578731548-c64695cc6952",
            },
            {
                "id": 3,
                "owner_id": 101,
                "community_id": 1,
                "name": "加厚鋁合金 A 字摺疊梯(6階)",
                "category": ItemCategory.HAND_TOOLS,
                "daily_rate": 90,
                "market_value": 1800,
                "damage_tool_id": "generic-aframe-ladder-6step",
                "status": ItemStatus.AVAILABLE,
                "accessories": ["折疊梯主體", "防滑橡膠腳墊", "頂部安全置物槽"],
                "safety_notes": "展開時務必確認每階卡榫完全彈出鎖定，嚴禁兩人同時攀登，最高兩階切勿站立。",
                "image_url": "/test_assets/ladder_checkin.jpg",
            },
            {
                "id": 4,
                "owner_id": 101,
                "community_id": 1,
                "name": "JMGO N1S Infinity 4K目氪三色雷射投影機",
                "category": ItemCategory.HAND_TOOLS,
                "daily_rate": 400,
                "market_value": 45000,
                "damage_tool_id": "jmgo-n1s-infinity-4k",
                "status": ItemStatus.AVAILABLE,
                "accessories": ["原廠遙控器", "專用電源供應器", "雲台旋轉底座", "便攜防撞箱"],
                "safety_notes": "三色雷射光束強烈，嚴禁直視投影鏡頭。關機後請待散熱風扇停止再收納。",
                "image_url": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c",
            },
            {
                "id": 5,
                "owner_id": 101,
                "community_id": 1,
                "name": "Snow Peak Land Nest 別墅帳 四人家庭隧道帳 TP-259",
                "category": ItemCategory.CAMPING,
                "daily_rate": 500,
                "market_value": 19800,
                "damage_tool_id": "snowpeak-landnest-tp259",
                "status": ItemStatus.AVAILABLE,
                "accessories": ["外帳本體", "內帳本體", "鋁合金主營柱x2", "A營柱x2", "原廠營釘x14", "營繩組"],
                "safety_notes": "嚴禁在密閉帳篷內使用炭火或瓦斯爐。歸還前請曬乾帳布並清除泥沙。",
                "image_url": "https://images.unsplash.com/photo-1478131143081-80f7f84ca84d",
            },
        ]

        for s_item in standard_items:
            existing = db.query(Item).filter(Item.id == s_item["id"]).first()
            if not existing:
                item_obj = Item(
                    id=s_item["id"],
                    owner_id=s_item["owner_id"],
                    community_id=s_item["community_id"],
                    name=s_item["name"],
                    category=s_item["category"],
                    daily_rate=s_item["daily_rate"],
                    market_value=s_item["market_value"],
                    damage_tool_id=s_item["damage_tool_id"],
                    status=s_item["status"],
                    accessories_json=json.dumps(s_item["accessories"], ensure_ascii=False),
                    safety_notes=s_item["safety_notes"],
                    image_url=s_item["image_url"],
                )
                db.add(item_obj)
        db.commit()

        # 4. 僅在資料庫完全無訂單時建立初始種子訂單 (避免伺服器重啟時將已結案訂單反覆覆寫為 IN_USE)
        has_any_orders = db.query(Order).first()
        if not has_any_orders:
            today = date.today()
            order1 = Order(
                order_no=f"ORD{today.strftime('%Y%m%d')}-DRILL1001",
                item_id=1,
                renter_id=102,
                lender_id=101,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=2),
                rent_days=3,
                daily_rate=150,
                total_rent=450,
                base_deposit=2250,
                actual_deposit=1125,
                status=OrderStatus.IN_USE,
                checkin_image_url="/test_assets/drill_checkin.jpg",
            )
            db.add(order1)

            order2 = Order(
                order_no=f"ORD{today.strftime('%Y%m%d')}-LADDER1002",
                item_id=3,
                renter_id=102,
                lender_id=101,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=1),
                rent_days=2,
                daily_rate=90,
                total_rent=180,
                base_deposit=1350,
                actual_deposit=675,
                status=OrderStatus.IN_USE,
                checkin_image_url="/test_assets/ladder_checkin.jpg",
            )
            db.add(order2)

        # 5. Ensure Initial Seed in Compensation Pool Ledger
        has_ledger = db.query(CompensationLedger).first()
        if not has_ledger:
            ledger = CompensationLedger(
                change_amount=20000,
                balance_after=20000,
                reason="INITIAL_SEED",
                notes="社區管理委員會創始提撥互助保障種子基金"
            )
            db.add(ledger)

        db.commit()
    except Exception as e:
        print(f"[Seed] Error seeding initial data: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    print("Seed data initialized successfully.")
