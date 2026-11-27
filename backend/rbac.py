import jwt
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth import decode_access_token
from database import get_db
from models import GroupMembership, Item, ItemGroup, User, UserSession


USER_ROLE = "user"
ADMIN_ROLE = "admin"

PERMISSION_ADMIN_ACCESS = "admin:access"
PERMISSION_CREATE_ITEM = "item:create"
PERMISSION_UPDATE_ITEM = "item:update"
PERMISSION_DELETE_ITEM = "item:delete"
PERMISSION_CREATE_GROUP = "group:create"

PERMISSION_GROUP_VIEW_ITEMS = "group:item:view"
PERMISSION_GROUP_CREATE_ITEM = "group:item:create"
PERMISSION_GROUP_EDIT_OWN_ITEM = "group:item:edit-own"
PERMISSION_GROUP_DELETE_OWN_ITEM = "group:item:delete-own"
PERMISSION_GROUP_EDIT_ANY_ITEM = "group:item:edit-any"
PERMISSION_GROUP_DELETE_ANY_ITEM = "group:item:delete-any"
PERMISSION_GROUP_MANAGE_SETTINGS = "group:manage-settings"
PERMISSION_GROUP_MANAGE_MEMBERS = "group:manage-members"

ROLE_PERMISSIONS = {
    USER_ROLE: frozenset({
        PERMISSION_CREATE_ITEM,
        PERMISSION_UPDATE_ITEM,
        PERMISSION_DELETE_ITEM,
        PERMISSION_CREATE_GROUP,
    }),
    ADMIN_ROLE: frozenset({
        PERMISSION_ADMIN_ACCESS,
        PERMISSION_CREATE_ITEM,
        PERMISSION_UPDATE_ITEM,
        PERMISSION_DELETE_ITEM,
        PERMISSION_CREATE_GROUP,
    }),
}

GROUP_ROLE_PERMISSIONS = {
    "owner": frozenset({
        PERMISSION_GROUP_VIEW_ITEMS,
        PERMISSION_GROUP_CREATE_ITEM,
        PERMISSION_GROUP_EDIT_ANY_ITEM,
        PERMISSION_GROUP_DELETE_ANY_ITEM,
        PERMISSION_GROUP_MANAGE_SETTINGS,
        PERMISSION_GROUP_MANAGE_MEMBERS,
    }),
    "member": frozenset({
        PERMISSION_GROUP_VIEW_ITEMS,
        PERMISSION_GROUP_CREATE_ITEM,
        PERMISSION_GROUP_EDIT_OWN_ITEM,
        PERMISSION_GROUP_DELETE_OWN_ITEM,
    }),
}

security = HTTPBearer(auto_error=False)


def is_datetime_expired(expires_at: datetime, now: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at <= now


def _authenticate(
    credentials: HTTPAuthorizationCredentials,
    db: Session
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
        token_id = payload["jti"]
        if not isinstance(token_id, str):
            raise TypeError("Invalid token identifier")
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    now = datetime.now(timezone.utc)
    user_session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user_id
    ).first()

    if (
        not user_session
        or user_session.revoked_at is not None
        or user_session.access_token_jti != token_id
        or is_datetime_expired(user_session.expires_at, now)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user or user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized"
        )

    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: Session = Depends(get_db)
) -> User | None:
    if credentials is None:
        return None

    return _authenticate(credentials, db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    return _authenticate(credentials, db)


def has_permission(user: User, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())


def require_permission(
    permission: str,
    detail: str = "Permission denied"
):
    def permission_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail
            )

        return current_user

    return permission_dependency


get_admin_user = require_permission(
    PERMISSION_ADMIN_ACCESS,
    "Admin access required"
)


def require_item_owner_or_admin(item: Item, current_user: User) -> None:
    if (
        item.user_id != current_user.id
        and not has_permission(current_user, PERMISSION_ADMIN_ACCESS)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )


def _get_group_and_role(
    db: Session,
    group_id: int,
    current_user: User
) -> tuple[ItemGroup, str]:
    group = db.query(ItemGroup).filter(
        ItemGroup.id == group_id,
        ItemGroup.archived_at.is_(None)
    ).first()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group.owner_id == current_user.id:
        return group, "owner"

    membership = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Group not found")

    return group, "member"


def require_group_permission(
    db: Session,
    group_id: int,
    current_user: User,
    permission: str
) -> ItemGroup:
    group, role = _get_group_and_role(db, group_id, current_user)

    if permission not in GROUP_ROLE_PERMISSIONS[role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    return group


def require_group_item_permission(
    db: Session,
    item: Item,
    current_user: User,
    action: str
) -> None:
    if item.group_id is None:
        require_item_owner_or_admin(item, current_user)
        return

    _, role = _get_group_and_role(db, item.group_id, current_user)
    if action == "edit":
        permission = (
            PERMISSION_GROUP_EDIT_ANY_ITEM
            if role == "owner"
            else PERMISSION_GROUP_EDIT_OWN_ITEM
        )
    elif action == "delete":
        permission = (
            PERMISSION_GROUP_DELETE_ANY_ITEM
            if role == "owner"
            else PERMISSION_GROUP_DELETE_OWN_ITEM
        )
    else:
        raise ValueError(f"Unsupported group item action: {action}")

    if permission not in GROUP_ROLE_PERMISSIONS[role]:
        raise HTTPException(status_code=403, detail="Permission denied")

    if role == "member" and item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
