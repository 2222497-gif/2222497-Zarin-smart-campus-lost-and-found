
from pathlib import Path
import os
from datetime import datetime, timedelta, timezone
import json
import csv
import io
from urllib.parse import urlsplit

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    Request
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from sqlalchemy import and_, desc, func, inspect, or_, text
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import (
    AuditLog,
    GroupMembership,
    Item,
    ItemGroup,
    LoginAttempt,
    User,
    UserSession
)
from auth import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    create_token_id
)
from rbac import (
    ADMIN_ROLE,
    USER_ROLE,
    get_current_user,
    get_optional_current_user,
    get_admin_user,
    is_datetime_expired,
    require_group_item_permission,
    require_group_permission,
    PERMISSION_CREATE_GROUP,
    PERMISSION_GROUP_CREATE_ITEM,
    PERMISSION_GROUP_MANAGE_MEMBERS,
    PERMISSION_GROUP_MANAGE_SETTINGS,
    PERMISSION_GROUP_VIEW_ITEMS,
    has_permission
)
from schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    RefreshRequest,
    UserSessionResponse,
    ProfileUpdate,
    PasswordChange,
    RoleUpdate,
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    ItemGroupCreate,
    ItemGroupUpdate,
    ItemGroupResponse,
    GroupMemberCreate,
    GroupMemberResponse,
    GroupDeleteConfirmation,
    AdminUserResponse,
    LoginAttemptResponse,
    AuditLogResponse
)
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Campus Lost and Found API")

def get_allowed_origins(
    configured_origins: str,
    is_production: bool
) -> list[str]:
    origins = list(dict.fromkeys(
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ))

    if is_production:
        origins = [
            origin for origin in origins
            if urlsplit(origin).hostname not in {
                "localhost",
                "127.0.0.1",
                "::1"
            }
        ]
    else:
        for local_origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ):
            if local_origin not in origins:
                origins.append(local_origin)

    return origins


is_production = (
    os.getenv("APP_ENV", "development").lower() == "production"
    or os.getenv("VERCEL") == "1"
    or os.getenv("VERCEL_ENV") in {"preview", "production"}
)
allowed_origins = get_allowed_origins(
    os.getenv("FRONTEND_ORIGIN", ""),
    is_production
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def create_new_tables():
    Base.metadata.create_all(bind=engine)
    ensure_item_group_column(engine)


def ensure_item_group_column(database_engine):
    if database_engine.dialect.name == "postgresql":
        with database_engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE items "
                "ADD COLUMN IF NOT EXISTS "
                "group_id INTEGER REFERENCES item_groups(id)"
            ))
    else:
        item_columns = {
            column["name"]
            for column in inspect(database_engine).get_columns("items")
        }

        if "group_id" not in item_columns:
            with database_engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE items "
                    "ADD COLUMN group_id INTEGER REFERENCES item_groups(id)"
                ))

    with database_engine.begin() as connection:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_items_group_id "
            "ON items (group_id)"
        ))


def write_audit_log(
    db: Session,
    actor_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: str | None = None
):
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )
    db.add(log)
    db.commit()


def write_login_audit(
    db: Session,
    action: str,
    email: str,
    user_id: int | None,
    ip_address: str | None,
    user_agent: str | None
):
    write_audit_log(
        db,
        None,
        action,
        "user",
        user_id,
        json.dumps({
            "email": email,
            "ip_address": ip_address,
            "user_agent": user_agent
        })
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/db-health")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        return {"database": "disconnected"}


@app.get("/api/hello")
def hello(name: str = "World"):
    return {"message": f"Hello, {name}!"}


@app.post(
    "/api/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=USER_ROLE
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    write_audit_log(
        db,
        new_user.id,
        "USER_REGISTERED",
        "user",
        new_user.id
    )

    return new_user


@app.post("/api/login", response_model=TokenResponse)
def login_user(
    user_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=15)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.email == user_data.email,
        LoginAttempt.success.is_(False),
        LoginAttempt.created_at >= cutoff
    ).count()

    if recent_failures >= 5:
        write_login_audit(
            db,
            "LOGIN_RATE_LIMITED",
            user_data.email,
            None,
            ip_address,
            user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again after 15 minutes."
        )

    user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if not user or not verify_password(
        user_data.password,
        user.password_hash
    ):
        db.add(
            LoginAttempt(
                user_id=user.id if user else None,
                email=user_data.email,
                success=False,
                ip_address=ip_address
            )
        )
        db.commit()
        write_login_audit(
            db,
            "LOGIN_FAILED",
            user_data.email,
            user.id if user else None,
            ip_address,
            user_agent
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if user.is_banned:
        db.add(
            LoginAttempt(
                user_id=user.id,
                email=user_data.email,
                success=False,
                ip_address=ip_address
            )
        )
        db.commit()
        write_login_audit(
            db,
            "LOGIN_BLOCKED_BANNED",
            user_data.email,
            user.id,
            ip_address,
            user_agent
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned"
        )

    db.add(
        LoginAttempt(
            user_id=user.id,
            email=user_data.email,
            success=True,
            ip_address=ip_address
        )
    )
    db.commit()

    refresh_token = create_refresh_token()
    token_id = create_token_id()
    user_session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        access_token_jti=token_id,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(user_session)
    db.flush()

    access_token = create_access_token(
        user.id,
        user.role,
        user_session.id,
        token_id
    )
    db.commit()

    write_audit_log(
        db,
        user.id,
        "USER_LOGIN",
        "user",
        user.id,
        json.dumps({
            "ip_address": ip_address,
            "user_agent": user_agent
        })
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "session_id": user_session.id,
        "token_type": "bearer"
    }


@app.post("/api/refresh", response_model=TokenResponse)
def refresh_session(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    user_session = db.query(UserSession).filter(
        UserSession.refresh_token_hash
        == hash_refresh_token(refresh_data.refresh_token)
    ).with_for_update().first()

    if (
        not user_session
        or user_session.revoked_at is not None
        or is_datetime_expired(user_session.expires_at, now)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired"
        )

    user = db.query(User).filter(User.id == user_session.user_id).first()
    if not user or user.is_banned:
        user_session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized"
        )

    refresh_token = create_refresh_token()
    token_id = create_token_id()
    user_session.refresh_token_hash = hash_refresh_token(refresh_token)
    user_session.access_token_jti = token_id
    user_session.expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        user.id,
        user.role,
        user_session.id,
        token_id
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "session_id": user_session.id,
        "token_type": "bearer"
    }


@app.post("/api/logout")
def logout_session(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db)
):
    user_session = db.query(UserSession).filter(
        UserSession.refresh_token_hash
        == hash_refresh_token(refresh_data.refresh_token)
    ).first()

    if user_session and user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
        write_audit_log(
            db,
            user_session.user_id,
            "USER_LOGOUT",
            "session",
            user_session.id
        )

    return {"message": "Logged out successfully"}


@app.get("/api/sessions", response_model=list[UserSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(UserSession).filter(
        UserSession.user_id == current_user.id
    ).order_by(desc(UserSession.created_at)).all()


@app.delete("/api/sessions/{session_id}")
def revoke_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()

    if not user_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
        write_audit_log(
            db,
            current_user.id,
            "SESSION_REVOKED",
            "session",
            user_session.id
        )

    return {"message": "Session revoked successfully"}


@app.get("/api/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user


@app.patch("/api/me", response_model=UserResponse)
def update_my_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    changes = profile_data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="No profile changes provided"
        )

    if "email" in changes:
        existing = db.query(User).filter(
            User.email == changes["email"],
            User.id != current_user.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Email already registered"
            )

    for key, value in changes.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    write_audit_log(
        db,
        current_user.id,
        "PROFILE_UPDATED",
        "user",
        current_user.id
    )

    return current_user


@app.post("/api/me/password")
def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(
        password_data.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    current_user.password_hash = hash_password(
        password_data.new_password
    )

    db.commit()

    write_audit_log(
        db,
        current_user.id,
        "PASSWORD_CHANGED",
        "user",
        current_user.id
    )

    return {"message": "Password changed successfully"}


@app.post("/api/groups", response_model=ItemGroupResponse, status_code=201)
def create_group(
    group_data: ItemGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_permission(current_user, PERMISSION_CREATE_GROUP):
        raise HTTPException(status_code=403, detail="Permission denied")

    group = ItemGroup(
        **group_data.model_dump(),
        owner_id=current_user.id
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    write_audit_log(
        db,
        current_user.id,
        "GROUP_CREATED",
        "group",
        group.id
    )
    return group


@app.get("/api/groups", response_model=list[ItemGroupResponse])
def get_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return (
        db.query(ItemGroup)
        .outerjoin(
            GroupMembership,
            and_(
                GroupMembership.group_id == ItemGroup.id,
                GroupMembership.user_id == current_user.id
            )
        )
        .filter(
            ItemGroup.archived_at.is_(None),
            or_(
                ItemGroup.owner_id == current_user.id,
                GroupMembership.user_id == current_user.id
            )
        )
        .distinct()
        .order_by(desc(ItemGroup.created_at))
        .all()
    )


@app.get("/api/groups/{group_id}", response_model=ItemGroupResponse)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_VIEW_ITEMS
    )


@app.patch("/api/groups/{group_id}", response_model=ItemGroupResponse)
def update_group(
    group_id: int,
    group_data: ItemGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_MANAGE_SETTINGS
    )
    updates = group_data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No group changes provided")
    if any(value is None for value in updates.values()):
        raise HTTPException(status_code=422, detail="Group fields cannot be null")

    for key, value in updates.items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)

    write_audit_log(
        db,
        current_user.id,
        "GROUP_UPDATED",
        "group",
        group.id,
        json.dumps({"fields": sorted(updates)})
    )
    return group


@app.delete("/api/groups/{group_id}")
def archive_group(
    group_id: int,
    confirmation: GroupDeleteConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_MANAGE_SETTINGS
    )
    if not confirmation.confirm:
        raise HTTPException(
            status_code=400,
            detail="Group deletion must be confirmed"
        )

    group.archived_at = datetime.now(timezone.utc)
    db.commit()
    write_audit_log(
        db,
        current_user.id,
        "GROUP_ARCHIVED",
        "group",
        group.id
    )
    return {"message": "Group archived; its item records were preserved"}


@app.get(
    "/api/groups/{group_id}/members",
    response_model=list[GroupMemberResponse]
)
def get_group_members(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_MANAGE_MEMBERS
    )
    return (
        db.query(
            GroupMembership.user_id.label("user_id"),
            User.name.label("name"),
            User.email.label("email"),
            GroupMembership.created_at.label("created_at")
        )
        .join(User, User.id == GroupMembership.user_id)
        .filter(GroupMembership.group_id == group_id)
        .order_by(User.name)
        .all()
    )


@app.post(
    "/api/groups/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=201
)
def add_group_member(
    group_id: int,
    member_data: GroupMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_MANAGE_MEMBERS
    )
    member = db.query(User).filter(
        func.lower(User.email) == str(member_data.email).lower()
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="User not found")
    if member.is_banned:
        raise HTTPException(
            status_code=409,
            detail="Banned users cannot be added to a group"
        )
    if member.id == group.owner_id:
        raise HTTPException(status_code=409, detail="User already owns this group")
    if db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == member.id
    ).first():
        raise HTTPException(
            status_code=409,
            detail="User is already a group member"
        )

    membership = GroupMembership(
        group_id=group_id,
        user_id=member.id
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    write_audit_log(
        db,
        current_user.id,
        "GROUP_MEMBER_ADDED",
        "group",
        group_id,
        json.dumps({"member_id": member.id})
    )
    return {
        "user_id": member.id,
        "name": member.name,
        "email": member.email,
        "created_at": membership.created_at
    }


@app.delete("/api/groups/{group_id}/members/{user_id}")
def remove_group_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_group_permission(
        db,
        group_id,
        current_user,
        PERMISSION_GROUP_MANAGE_MEMBERS
    )
    membership = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Group member not found")

    db.delete(membership)
    db.commit()
    write_audit_log(
        db,
        current_user.id,
        "GROUP_MEMBER_REMOVED",
        "group",
        group_id,
        json.dumps({"member_id": user_id})
    )
    return {"message": "Group member removed"}


@app.post("/api/items", response_model=ItemResponse, status_code=201)
def create_item(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if item_data.group_id is not None:
        require_group_permission(
            db,
            item_data.group_id,
            current_user,
            PERMISSION_GROUP_CREATE_ITEM
        )

    new_item = Item(
        **item_data.model_dump(),
        user_id=current_user.id
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    write_audit_log(
        db,
        current_user.id,
        "ITEM_CREATED",
        "item",
        new_item.id,
        json.dumps({"group_id": new_item.group_id})
    )

    return new_item


@app.get("/api/items", response_model=list[ItemResponse])
def get_items(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)
):
    query = db.query(Item)
    if current_user is None:
        query = query.filter(Item.group_id.is_(None))
    else:
        accessible_group_ids = (
            db.query(ItemGroup.id)
            .outerjoin(
                GroupMembership,
                and_(
                    GroupMembership.group_id == ItemGroup.id,
                    GroupMembership.user_id == current_user.id
                )
            )
            .filter(
                ItemGroup.archived_at.is_(None),
                or_(
                    ItemGroup.owner_id == current_user.id,
                    GroupMembership.user_id == current_user.id
                )
            )
        )
        query = query.filter(
            or_(
                Item.group_id.is_(None),
                Item.group_id.in_(accessible_group_ids)
            )
        )

    return query.order_by(desc(Item.created_at)).all()


@app.get("/api/items/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)
):
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    if item.group_id is not None:
        if current_user is None:
            raise HTTPException(status_code=404, detail="Item not found")
        require_group_permission(
            db,
            item.group_id,
            current_user,
            PERMISSION_GROUP_VIEW_ITEMS
        )

    return item


@app.put("/api/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    item_data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    require_group_item_permission(db, item, current_user, "edit")

    for key, value in item_data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)

    write_audit_log(
        db,
        current_user.id,
        "ITEM_UPDATED",
        "item",
        item.id,
        json.dumps({"group_id": item.group_id})
    )

    return item


@app.delete("/api/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    require_group_item_permission(db, item, current_user, "delete")

    item_id_to_log = item.id
    group_id_to_log = item.group_id

    db.delete(item)
    db.commit()

    write_audit_log(
        db,
        current_user.id,
        "ITEM_DELETED",
        "item",
        item_id_to_log,
        json.dumps({"group_id": group_id_to_log})
    )

    return {"message": "Item deleted successfully"}


# ADMIN ROUTES


@app.get("/api/admin/stats")
def admin_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    total_users = db.query(User).count()
    total_items = db.query(Item).count()
    banned_users = db.query(User).filter(
        User.is_banned.is_(True)
    ).count()
    admin_users = db.query(User).filter(
        User.role == ADMIN_ROLE
    ).count()
    lost_items = db.query(Item).filter(
        Item.item_type == "Lost"
    ).count()
    found_items = db.query(Item).filter(
        Item.item_type == "Found"
    ).count()

    return {
        "total_users": total_users,
        "total_items": total_items,
        "banned_users": banned_users,
        "admin_users": admin_users,
        "lost_items": lost_items,
        "found_items": found_items
    }


@app.get("/api/admin/users", response_model=list[AdminUserResponse])
def admin_get_users(
    search: str = "",
    role: str | None = None,
    banned: bool | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid pagination values"
        )

    query = db.query(User)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_term)) |
            (User.email.ilike(search_term))
        )

    if role:
        query = query.filter(User.role == role)

    if banned is not None:
        query = query.filter(User.is_banned.is_(banned))

    return query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()


@app.patch("/api/admin/users/{user_id}/ban")
def admin_ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot ban your own account"
        )

    user.is_banned = True
    db.commit()

    write_audit_log(
        db,
        admin.id,
        "USER_BANNED",
        "user",
        user.id
    )

    return {"message": "User banned successfully"}


@app.patch("/api/admin/users/{user_id}/unban")
def admin_unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_banned = False
    db.commit()

    write_audit_log(
        db,
        admin.id,
        "USER_UNBANNED",
        "user",
        user.id
    )

    return {"message": "User unbanned successfully"}


@app.patch("/api/admin/users/{user_id}/role")
def admin_change_role(
    user_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if role_data.role not in [USER_ROLE, ADMIN_ROLE]:
        raise HTTPException(
            status_code=400,
            detail="Role must be user or admin"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id and role_data.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own admin role"
        )

    old_role = user.role
    user.role = role_data.role
    db.commit()

    write_audit_log(
        db,
        admin.id,
        "USER_ROLE_CHANGED",
        "user",
        user.id,
        json.dumps({
            "old_role": old_role,
            "new_role": role_data.role
        })
    )

    return {"message": "User role updated successfully"}


@app.get(
    "/api/admin/login-attempts",
    response_model=list[LoginAttemptResponse]
)
def admin_login_attempts(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid pagination values"
        )

    return db.query(LoginAttempt).order_by(
        desc(LoginAttempt.created_at)
    ).offset(skip).limit(limit).all()


@app.get(
    "/api/admin/audit-logs",
    response_model=list[AuditLogResponse]
)
def admin_audit_logs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid pagination values"
        )

    return db.query(AuditLog).order_by(
        desc(AuditLog.created_at)
    ).offset(skip).limit(limit).all()


@app.get("/api/admin/audit-logs/export")
def export_audit_logs(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    logs = db.query(AuditLog).order_by(
        desc(AuditLog.created_at)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Actor ID",
        "Action",
        "Target Type",
        "Target ID",
        "Details",
        "Created At"
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.actor_id,
            log.action,
            log.target_type,
            log.target_id,
            log.details,
            log.created_at
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit_logs.csv"
        }
    )


# Frontend build directory

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend"
    )
