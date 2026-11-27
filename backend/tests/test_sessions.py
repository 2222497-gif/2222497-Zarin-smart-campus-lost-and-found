import unittest
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import ALGORITHM, SECRET_KEY
from database import Base, get_db
from main import app, ensure_item_group_column, get_allowed_origins
from models import Item, User


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
        )

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        self.original_startup_handlers = list(app.router.on_startup)
        app.router.on_startup.clear()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.router.on_startup.extend(self.original_startup_handlers)
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def register_and_login(self):
        registration = self.client.post(
            "/api/register",
            json={
                "name": "Session Tester",
                "email": "session@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(registration.status_code, 201)

        response = self.client.post(
            "/api/login",
            json={
                "email": "session@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def register_user_and_login(self, name, email):
        registration = self.client.post(
            "/api/register",
            json={
                "name": name,
                "email": email,
                "password": "valid-password-123",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        response = self.client.post(
            "/api/login",
            json={
                "email": email,
                "password": "valid-password-123",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_production_cors_excludes_local_origins(self):
        production_origins = get_allowed_origins(
            "https://campus.example, http://localhost:5173",
            is_production=True
        )
        self.assertEqual(production_origins, ["https://campus.example"])

        development_origins = get_allowed_origins(
            "",
            is_production=False
        )
        self.assertEqual(
            development_origins,
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        )

    def test_existing_item_table_migration_preserves_rows(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE item_groups (id INTEGER PRIMARY KEY)"
                ))
                connection.execute(text(
                    "CREATE TABLE items ("
                    "id INTEGER PRIMARY KEY, item_name TEXT NOT NULL)"
                ))
                connection.execute(text(
                    "INSERT INTO items (id, item_name) "
                    "VALUES (1, 'Existing lost item')"
                ))

            ensure_item_group_column(engine)

            columns = {
                column["name"]
                for column in inspect(engine).get_columns("items")
            }
            self.assertIn("group_id", columns)
            with engine.connect() as connection:
                row = connection.execute(text(
                    "SELECT id, item_name, group_id FROM items WHERE id = 1"
                )).one()
            self.assertEqual(row, (1, "Existing lost item", None))
        finally:
            engine.dispose()

    def test_missing_invalid_and_expired_access_tokens_return_401(self):
        login = self.register_and_login()
        expired_at = datetime.now(timezone.utc)
        expired_token = jwt.encode(
            {
                "sub": "1",
                "sid": str(login["session_id"]),
                "jti": "expired-token",
                "iat": expired_at - timedelta(minutes=2),
                "exp": expired_at - timedelta(minutes=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/me",
                headers={"Authorization": f"Bearer {login['access_token']}tampered"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            ).status_code,
            401,
        )

    def test_refresh_rotates_tokens_and_invalidates_previous_access(self):
        login = self.register_and_login()
        old_access_headers = {
            "Authorization": f"Bearer {login['access_token']}"
        }

        refresh = self.client.post(
            "/api/refresh",
            json={"refresh_token": login["refresh_token"]},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)
        refreshed = refresh.json()
        self.assertEqual(refreshed["session_id"], login["session_id"])
        self.assertEqual(
            self.client.get("/api/me", headers=old_access_headers).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/api/refresh",
                json={"refresh_token": login["refresh_token"]},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/me",
                headers={
                    "Authorization": f"Bearer {refreshed['access_token']}"
                },
            ).status_code,
            200,
        )

    def test_logout_and_session_revocation_invalidate_access(self):
        login = self.register_and_login()
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        sessions = self.client.get("/api/sessions", headers=headers)
        self.assertEqual(sessions.status_code, 200, sessions.text)
        self.assertEqual(len(sessions.json()), 1)

        revoked = self.client.delete(
            f"/api/sessions/{login['session_id']}",
            headers=headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(self.client.get("/api/me", headers=headers).status_code, 401)

        logout = self.client.post(
            "/api/logout",
            json={"refresh_token": login["refresh_token"]},
        )
        self.assertEqual(logout.status_code, 200, logout.text)

    def test_failed_login_is_included_in_admin_audit_csv(self):
        registration = self.client.post(
            "/api/register",
            json={
                "name": "Audit Tester",
                "email": "audit@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(registration.status_code, 201)

        failed_login = self.client.post(
            "/api/login",
            json={
                "email": "audit@example.com",
                "password": "wrong-password",
            },
        )
        self.assertEqual(failed_login.status_code, 401)

        db = self.session_local()
        try:
            admin_user = db.query(User).filter(
                User.email == "audit@example.com"
            ).first()
            admin_user.role = "admin"
            db.commit()
        finally:
            db.close()

        admin_login = self.client.post(
            "/api/login",
            json={
                "email": "audit@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(admin_login.status_code, 200)

        exported = self.client.get(
            "/api/admin/audit-logs/export",
            headers={
                "Authorization": (
                    f"Bearer {admin_login.json()['access_token']}"
                )
            },
        )
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn("LOGIN_FAILED", exported.text)
        self.assertIn("audit@example.com", exported.text)

    def test_admin_user_filters_and_pagination(self):
        admin_login = self.register_and_login()
        db = self.session_local()
        try:
            admin_user = db.query(User).filter(
                User.email == "session@example.com"
            ).first()
            admin_user.role = "admin"

            now = datetime.now(timezone.utc)
            for index in range(3):
                db.add(
                    User(
                        name=f"Paged User {index}",
                        email=f"paged-{index}@example.com",
                        password_hash="unused-for-listing",
                        role="user",
                        is_banned=False,
                        created_at=now - timedelta(minutes=index + 1),
                    )
                )
            db.commit()
        finally:
            db.close()

        headers = {
            "Authorization": f"Bearer {admin_login['access_token']}"
        }
        first_page = self.client.get(
            "/api/admin/users?role=user&banned=false&skip=0&limit=2",
            headers=headers,
        )
        second_page = self.client.get(
            "/api/admin/users?role=user&banned=false&skip=2&limit=2",
            headers=headers,
        )

        self.assertEqual(first_page.status_code, 200, first_page.text)
        self.assertEqual(second_page.status_code, 200, second_page.text)
        self.assertEqual(len(first_page.json()), 2)
        self.assertEqual(len(second_page.json()), 1)
        self.assertEqual(
            len({
                user["id"]
                for user in first_page.json() + second_page.json()
            }),
            3,
        )

    def test_role_and_item_ownership_permissions(self):
        first_user = self.register_and_login()
        second_registration = self.client.post(
            "/api/register",
            json={
                "name": "Second User",
                "email": "second@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(second_registration.status_code, 201)
        second_login = self.client.post(
            "/api/login",
            json={
                "email": "second@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(second_login.status_code, 200)

        owner_headers = {
            "Authorization": f"Bearer {second_login.json()['access_token']}"
        }
        other_headers = {
            "Authorization": f"Bearer {first_user['access_token']}"
        }
        created_item = self.client.post(
            "/api/items",
            headers=owner_headers,
            json={
                "item_name": "Lost keys",
                "item_type": "Lost",
                "location": "Library",
                "date": "2026-11-26",
                "description": "A set of keys",
                "contact": "123456789",
                "email": "second@example.com",
            },
        )
        self.assertEqual(created_item.status_code, 201, created_item.text)
        item_id = created_item.json()["id"]

        self.assertEqual(
            self.client.get(
                "/api/admin/stats",
                headers=other_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/items/{item_id}",
                headers=other_headers,
                json={"item_name": "Changed by another user"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/items/{item_id}",
                headers=other_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/items/{item_id}",
                headers=owner_headers,
                json={"item_name": "Updated by owner"},
            ).status_code,
            200,
        )

    def test_group_roles_visibility_membership_and_item_preservation(self):
        owner_login = self.register_and_login()
        member_login = self.register_user_and_login(
            "Group Member",
            "member@example.com"
        )
        outsider_login = self.register_user_and_login(
            "Group Outsider",
            "outsider@example.com"
        )
        owner_headers = {
            "Authorization": f"Bearer {owner_login['access_token']}"
        }
        member_headers = {
            "Authorization": f"Bearer {member_login['access_token']}"
        }
        outsider_headers = {
            "Authorization": f"Bearer {outsider_login['access_token']}"
        }

        group_response = self.client.post(
            "/api/groups",
            headers=owner_headers,
            json={"name": "Library Team", "description": "Shared reports"},
        )
        self.assertEqual(group_response.status_code, 201, group_response.text)
        group_id = group_response.json()["id"]

        added_member = self.client.post(
            f"/api/groups/{group_id}/members",
            headers=owner_headers,
            json={"email": "member@example.com"},
        )
        self.assertEqual(added_member.status_code, 201, added_member.text)
        self.assertEqual(added_member.json()["email"], "member@example.com")

        public_item = self.client.post(
            "/api/items",
            headers=owner_headers,
            json={
                "item_name": "Public notebook",
                "item_type": "Found",
                "location": "Library",
                "date": "2026-11-26",
                "description": "A blue notebook",
                "contact": "123456789",
                "email": "session@example.com",
            },
        )
        self.assertEqual(public_item.status_code, 201, public_item.text)
        public_item_id = public_item.json()["id"]

        member_item = self.client.post(
            "/api/items",
            headers=member_headers,
            json={
                "item_name": "Shared wallet",
                "item_type": "Lost",
                "location": "Library",
                "date": "2026-11-26",
                "description": "A brown wallet",
                "contact": "123456789",
                "email": "member@example.com",
                "group_id": group_id,
            },
        )
        self.assertEqual(member_item.status_code, 201, member_item.text)
        member_item_id = member_item.json()["id"]

        owner_item = self.client.post(
            "/api/items",
            headers=owner_headers,
            json={
                "item_name": "Shared keys",
                "item_type": "Found",
                "location": "Library",
                "date": "2026-11-26",
                "description": "A set of keys",
                "contact": "123456789",
                "email": "session@example.com",
                "group_id": group_id,
            },
        )
        self.assertEqual(owner_item.status_code, 201, owner_item.text)
        owner_item_id = owner_item.json()["id"]

        member_items = self.client.get(
            "/api/items",
            headers=member_headers
        ).json()
        self.assertEqual(
            {item["id"] for item in member_items},
            {public_item_id, member_item_id, owner_item_id}
        )
        outsider_items = self.client.get(
            "/api/items",
            headers=outsider_headers
        ).json()
        self.assertNotIn(
            member_item_id,
            {item["id"] for item in outsider_items}
        )
        anonymous_items = self.client.get("/api/items").json()
        self.assertIn(
            public_item_id,
            {item["id"] for item in anonymous_items}
        )
        self.assertNotIn(
            member_item_id,
            {item["id"] for item in anonymous_items}
        )
        self.assertEqual(
            self.client.get(
                f"/api/items/{member_item_id}",
                headers=outsider_headers
            ).status_code,
            404
        )
        self.assertEqual(
            self.client.put(
                f"/api/items/{owner_item_id}",
                headers=member_headers,
                json={"item_name": "Unauthorized edit"},
            ).status_code,
            403
        )
        self.assertEqual(
            self.client.patch(
                f"/api/groups/{group_id}",
                headers=member_headers,
                json={"name": "Member edit"},
            ).status_code,
            403
        )
        self.assertEqual(
            self.client.put(
                f"/api/items/{member_item_id}",
                headers=member_headers,
                json={"item_name": "Member updated own item"},
            ).status_code,
            200
        )
        self.assertEqual(
            self.client.put(
                f"/api/items/{member_item_id}",
                headers=owner_headers,
                json={"item_name": "Owner managed item"},
            ).status_code,
            200
        )

        db = self.session_local()
        try:
            member_id = db.query(User).filter(
                User.email == "member@example.com"
            ).first().id
        finally:
            db.close()
        removed = self.client.delete(
            f"/api/groups/{group_id}/members/{member_id}",
            headers=owner_headers,
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(
            self.client.get(
                f"/api/items/{member_item_id}",
                headers=member_headers
            ).status_code,
            404
        )
        self.assertEqual(
            self.client.get(
                f"/api/items/{member_item_id}",
                headers=owner_headers
            ).status_code,
            200
        )

    def test_archiving_group_requires_confirmation_and_preserves_items(self):
        owner_login = self.register_and_login()
        owner_headers = {
            "Authorization": f"Bearer {owner_login['access_token']}"
        }
        group_response = self.client.post(
            "/api/groups",
            headers=owner_headers,
            json={"name": "Archive Test", "description": ""},
        )
        self.assertEqual(group_response.status_code, 201, group_response.text)
        group_id = group_response.json()["id"]

        item_response = self.client.post(
            "/api/items",
            headers=owner_headers,
            json={
                "item_name": "Archived group item",
                "item_type": "Lost",
                "location": "Hall",
                "date": "2026-11-26",
                "description": "An item in an archived group",
                "contact": "123456789",
                "email": "session@example.com",
                "group_id": group_id,
            },
        )
        self.assertEqual(item_response.status_code, 201, item_response.text)
        item_id = item_response.json()["id"]

        self.assertEqual(
            self.client.request(
                "DELETE",
                f"/api/groups/{group_id}",
                headers=owner_headers,
                json={"confirm": False},
            ).status_code,
            400
        )
        archived = self.client.request(
            "DELETE",
            f"/api/groups/{group_id}",
            headers=owner_headers,
            json={"confirm": True},
        )
        self.assertEqual(archived.status_code, 200, archived.text)

        db = self.session_local()
        try:
            stored_item = db.query(Item).filter(Item.id == item_id).first()
            self.assertIsNotNone(stored_item)
            self.assertEqual(stored_item.group_id, group_id)
        finally:
            db.close()

        self.assertEqual(
            self.client.get(
                f"/api/items/{item_id}",
                headers=owner_headers
            ).status_code,
            404
        )


if __name__ == "__main__":
    unittest.main()
