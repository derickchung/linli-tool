import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)



class VerificationStatus(str, enum.Enum):
    VALIDATED = "VALIDATED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class ItemCategory(str, enum.Enum):
    POWER_TOOLS = "POWER_TOOLS"
    CLEANING = "CLEANING"
    CAMPING = "CAMPING"
    GARDENING = "GARDENING"
    HAND_TOOLS = "HAND_TOOLS"


class ItemStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RENTED = "RENTED"
    MAINTENANCE = "MAINTENANCE"
    DECOMMISSIONED = "DECOMMISSIONED"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PICKED_UP = "PICKED_UP"
    IN_USE = "IN_USE"
    INSPECTION = "INSPECTION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


class DisputeStatus(str, enum.Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    members = relationship("User", back_populates="community")
    items = relationship("Item", back_populates="community")
    invitations = relationship("CommunityInvitation", back_populates="community")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False, default="鄰里住戶")
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=True)
    verification_status = Column(
        Enum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False
    )
    credit_score = Column(Integer, default=80, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    community = relationship("Community", back_populates="members")
    owned_items = relationship("Item", back_populates="owner")
    borrowed_orders = relationship(
        "Order", foreign_keys="Order.renter_id", back_populates="renter"
    )
    lent_orders = relationship(
        "Order", foreign_keys="Order.lender_id", back_populates="lender"
    )


class CommunityInvitation(Base):
    __tablename__ = "community_invitations"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    inviter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    inviter = relationship("User")
    community = relationship("Community", back_populates="invitations")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(Enum(ItemCategory), nullable=False, default=ItemCategory.HAND_TOOLS)
    daily_rate = Column(Integer, nullable=False)
    market_value = Column(Integer, nullable=False)
    damage_tool_id = Column(String(50), nullable=True)
    status = Column(Enum(ItemStatus), default=ItemStatus.AVAILABLE, nullable=False)
    accessories_json = Column(Text, default="[]")
    safety_notes = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    owner = relationship("User", back_populates="owned_items")
    community = relationship("Community", back_populates="items")
    orders = relationship("Order", back_populates="item")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, index=True, nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    renter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    rent_days = Column(Integer, nullable=False)
    daily_rate = Column(Integer, nullable=False)
    total_rent = Column(Integer, nullable=False)
    base_deposit = Column(Integer, nullable=False)
    actual_deposit = Column(Integer, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)

    handover_code = Column(String(10), nullable=True)
    handover_code_expires = Column(DateTime, nullable=True)
    checkin_image_url = Column(Text, nullable=True)
    checkout_image_url = Column(Text, nullable=True)
    vision_result = Column(String(30), nullable=True)
    compensation_amount = Column(Integer, default=0)
    pool_payout = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)

    item = relationship("Item", back_populates="orders")
    renter = relationship("User", foreign_keys=[renter_id], back_populates="borrowed_orders")
    lender = relationship("User", foreign_keys=[lender_id], back_populates="lent_orders")
    dispute = relationship("DisputeTicket", uselist=False, back_populates="order")


class DisputeTicket(Base):
    __tablename__ = "dispute_tickets"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    complainant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(DisputeStatus), default=DisputeStatus.OPEN, nullable=False)
    evidence_photos = Column(Text, default="[]")
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    resolved_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="dispute")
    complainant = relationship("User")


class CompensationLedger(Base):
    """平台損壞互助保障池流水帳本 (Audit Ledger)"""
    __tablename__ = "compensation_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    change_amount = Column(Integer, nullable=False)  # 正值為提撥入池，負值為補貼支出
    balance_after = Column(Integer, nullable=False)  # 異動後即時餘額 (保證 >= 0)
    reason = Column(String(100), nullable=False)     # 如 PLATFORM_FEE_CONTRIBUTION, DAMAGE_COMPENSATION_PAYOUT, INITIAL_SEED
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    order = relationship("Order")

