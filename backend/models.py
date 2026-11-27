
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    items = relationship("Item", back_populates="owner")
    owned_groups = relationship("ItemGroup", back_populates="owner")
    group_memberships = relationship("GroupMembership", back_populates="user")


class ItemGroup(Base):
    __tablename__ = "item_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="owned_groups")
    memberships = relationship("GroupMembership", back_populates="group")
    items = relationship("Item", back_populates="group")


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer,
        ForeignKey("item_groups.id"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    group = relationship("ItemGroup", back_populates="memberships")
    user = relationship("User", back_populates="group_memberships")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(150), nullable=False)
    item_type = Column(String(20), nullable=False)
    location = Column(String(255), nullable=False)
    date = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    contact = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False)
    image = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(
        Integer,
        ForeignKey("item_groups.id"),
        nullable=True,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    owner = relationship("User", back_populates="items")
    group = relationship("ItemGroup", back_populates="items")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=False)
    ip_address = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    refresh_token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True
    )
    access_token_jti = Column(String(64), nullable=False)
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
