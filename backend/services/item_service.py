import json
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models import Item, User, ItemStatus, ItemCategory, VerificationStatus
from ..schemas import ItemCreate, ItemUpdate, ItemResponse


def parse_accessories(accessories_json: Optional[str]) -> List[str]:
    if not accessories_json:
        return []
    try:
        data = json.loads(accessories_json)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except Exception:
        return []


def to_item_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        owner_id=item.owner_id,
        owner_name=item.owner.name if item.owner else None,
        community_id=item.community_id,
        name=item.name,
        category=item.category.value if hasattr(item.category, "value") else str(item.category),
        daily_rate=item.daily_rate,
        market_value=item.market_value,
        damage_tool_id=item.damage_tool_id,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        accessories=parse_accessories(item.accessories_json),
        safety_notes=item.safety_notes,
        image_url=item.image_url,
        created_at=item.created_at,
    )


def create_item(db: Session, user: User, item_in: ItemCreate) -> Item:
    if user.verification_status != VerificationStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅已驗證住戶可上架工具，請先完成社區擔保驗證。",
        )
    if not user.community_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="使用者尚未綁定社區，無法上架工具。",
        )
    if item_in.market_value < 100 or item_in.market_value > 100000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="商品原價 market_value 必須介於 100 至 100,000 元之間。",
        )

    accessories_str = json.dumps(item_in.accessories or [], ensure_ascii=False)

    item = Item(
        owner_id=user.id,
        community_id=user.community_id,
        name=item_in.name,
        category=ItemCategory(item_in.category),
        daily_rate=item_in.daily_rate,
        market_value=item_in.market_value,
        damage_tool_id=item_in.damage_tool_id,
        status=ItemStatus.AVAILABLE,
        accessories_json=accessories_str,
        safety_notes=item_in.safety_notes,
        image_url=item_in.image_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: int, current_user: Optional[User] = None) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {item_id} 的工具項目。",
        )
    if current_user and current_user.community_id != item.community_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="跨社區資料隔離保護：您無權限查看非所屬社區之工具。",
        )
    return item


def list_items(
    db: Session,
    community_id: int,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    query: Optional[str] = None,
) -> Tuple[List[Item], List[str]]:
    q = db.query(Item).filter(Item.community_id == community_id)

    if status_filter and status_filter.upper() != "ALL":
        try:
            status_enum = ItemStatus(status_filter)
            q = q.filter(Item.status == status_enum)
        except ValueError:
            pass

    if category:
        try:
            cat_enum = ItemCategory(category)
            q = q.filter(Item.category == cat_enum)
        except ValueError:
            pass

    inferred_tags: List[str] = []
    if query:
        term = f"%{query.strip()}%"
        q = q.filter(or_(Item.name.ilike(term), Item.safety_notes.ilike(term)))
        inferred_tags.append(query.strip())

    items = q.order_by(Item.id.desc()).all()
    return items, inferred_tags


def update_item_status(db: Session, item_id: int, new_status: str, user: User) -> Item:
    item = get_item(db, item_id, current_user=user)
    if item.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅工具擁有者有權限修改工具狀態。",
        )
    try:
        item.status = ItemStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無效的工具狀態: {new_status}",
        )
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, item_in: ItemUpdate, user: User) -> Item:
    item = get_item(db, item_id, current_user=user)
    if item.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅工具擁有者有權限修改工具資訊。",
        )
    if item_in.name is not None:
        item.name = item_in.name
    if item_in.category is not None:
        item.category = ItemCategory(item_in.category)
    if item_in.daily_rate is not None:
        item.daily_rate = item_in.daily_rate
    if item_in.market_value is not None:
        if item_in.market_value < 100 or item_in.market_value > 100000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="商品原價 market_value 必須介於 100 至 100,000 元之間。",
            )
        item.market_value = item_in.market_value
    if item_in.damage_tool_id is not None:
        item.damage_tool_id = item_in.damage_tool_id
    if item_in.accessories is not None:
        item.accessories_json = json.dumps(item_in.accessories, ensure_ascii=False)
    if item_in.safety_notes is not None:
        item.safety_notes = item_in.safety_notes
    if item_in.image_url is not None:
        item.image_url = item_in.image_url

    db.commit()
    db.refresh(item)
    return item
