
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    session_id: int
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class UserSessionResponse(BaseModel):
    id: int
    created_at: object
    expires_at: object
    revoked_at: object | None
    ip_address: str | None
    user_agent: str | None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class RoleUpdate(BaseModel):
    role: str


class ItemCreate(BaseModel):
    item_name: str = Field(min_length=2, max_length=150)
    item_type: str
    location: str = Field(min_length=2, max_length=255)
    date: str
    description: str = Field(min_length=5)
    contact: str
    email: EmailStr
    image: str | None = None
    group_id: int | None = None


class ItemUpdate(BaseModel):
    item_name: str | None = None
    item_type: str | None = None
    location: str | None = None
    date: str | None = None
    description: str | None = None
    contact: str | None = None
    email: EmailStr | None = None
    image: str | None = None


class ItemResponse(BaseModel):
    id: int
    item_name: str
    item_type: str
    location: str
    date: str
    description: str
    contact: str
    email: EmailStr
    image: str | None
    user_id: int
    group_id: int | None

    model_config = ConfigDict(from_attributes=True)


class ItemGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)


class ItemGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class ItemGroupResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class GroupMemberCreate(BaseModel):
    email: EmailStr


class GroupMemberResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    created_at: object


class GroupDeleteConfirmation(BaseModel):
    confirm: bool


class AdminUserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    is_banned: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class LoginAttemptResponse(BaseModel):
    id: int
    user_id: int | None
    email: str
    success: bool
    ip_address: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    details: str | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)
