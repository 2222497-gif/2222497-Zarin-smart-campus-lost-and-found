# Smart Campus Lost and Found — Project Report

## 1. Product Requirements Document (PRD)

### Problem and users

Students need a shared place to report, search, and recover lost or found
campus items. Regular users manage their own reports and account; group owners
and members share group-scoped reports; administrators monitor users and
platform activity.

### Product scope

- Register and log in using a short-lived access token and a refreshable,
  revocable server-side session.
- Create, browse, search/filter, edit, and delete lost/found item reports.
- Optionally share a report with a group while retaining its creator.
- Apply fixed group permissions: members create and view shared items and
  manage only their own items; owners manage all group items, settings, and
  membership.
- Provide administrator statistics, user/role/ban management, login history,
  audit-log review, and CSV export.
- Deploy the React frontend and FastAPI API through Vercel Services.

### Out of scope

- Configurable per-member group permissions.
- Moving or transferring item ownership when group membership changes.
- Deleting item records when a group is archived.

## 2. Software Requirements Specification (SRS)

### System components

- Frontend: React, TypeScript, Vite.
- Backend: FastAPI, Pydantic, SQLAlchemy.
- Persistence: PostgreSQL-compatible database (Neon is intended for deployment).
- Hosting: Vercel Services with `/api/*` routed to FastAPI and other paths to
  the Vite frontend.

### Main data entities

- `User`: account identity, password hash, role, and ban status.
- `UserSession`: hashed refresh token, active access-token ID, expiry, and
  revocation metadata.
- `Item`: lost/found report and immutable creator association; optional
  `group_id` identifies a shared report.
- `ItemGroup`: name, description, owner, creation time, and archive time.
- `GroupMembership`: unique group/user membership.
- `LoginAttempt` and `AuditLog`: authentication and security/activity records.

### Authorization rules

- Protected API operations validate the bearer JWT and active server-side
  session; invalid/expired credentials receive 401 and unauthorized actions
  receive 403 (or 404 where group/item existence is intentionally concealed).
- Admin routes use reusable permission checks.
- Public, ungrouped reports remain available for compatibility.
- Group reports require active membership; removal revokes access without
  deleting or transferring the report.
- Group item edits/deletes are allowed to the creator or the owning group owner.
  An administrator does not bypass group membership for group-scoped items.
- Group deletion is owner-only and confirmed; it archives the group while
  preserving report rows.

### Schema update behavior

SQLAlchemy `create_all()` creates missing tables, but does not add columns to
existing tables. Startup therefore applies an additive update for nullable
`items.group_id` (with an index) after creating the group tables. Existing item
rows remain ungrouped and unchanged. The migration helper is covered by a
SQLite test; the production Neon schema has not been inspected or migrated in
this run because production database credentials are not configured in Vercel.

## 3. Technical Design Document (TDD)

### Authentication and sessions

Access tokens carry user, session, token-ID, issue-time, and expiry claims.
Backend dependencies validate the JWT and compare the token ID/session state
with the database. Refresh tokens are opaque, stored only as hashes, and
rotated. Logout and session revocation invalidate access tokens.

### Group and item flow

Group routes verify the authenticated owner/member before returning group data
or changing group state. Item creation sets `user_id` from the authenticated
user; client input cannot select a creator. Group item reads are filtered by
membership. The shared RBAC helper verifies group membership, group role, and
creator ownership for edits/deletes.

### Deployment topology

`vercel.json` declares the `frontend` and `backend` services and routes public
traffic. The linked project is `campus-lost-found-medha`, with root directory
`.` and the `Services` preset. The older `2222497_` project is connected to the
GitHub repository and is not the selected deployment target.

## 4. Verification and Current Deployment Status

### Locally verified

- Backend unit tests cover authentication/session lifecycle, admin filtering
  and audit CSV, group membership/ownership, archive/removal data preservation,
  CORS selection, and additive migration of an existing items table.
- Frontend production build: passed from `frontend/` using `npm run build`.
- Backend test suite: 10 tests passed.
- Python compilation and `git diff --check`: passed.

### Vercel verified / blocked

- Vercel CLI is authenticated as the repository owner.
- The correct `campus-lost-found-medha` project has a prior READY production
  deployment and the `/api/health` endpoint returned `{"status":"ok"}` through
  authenticated Vercel access.
- The existing deployment redirects unauthenticated visitors to Vercel SSO.
- The project currently has no production environment variables and is not
  connected to a Git repository.
- A local `vercel build` attempt was blocked by Windows symlink permission
  errors in Vercel's builder cache. This is separate from the Vite production
  build and does not prove a hosted build will fail.
- The latest source is committed and pushed to `medha-frontend`, but the
  unconnected Vercel project did not auto-deploy it.
- No production deployment of the latest source, public access change, or live
  Neon schema update has been completed.

### Required manual production setup

In the `campus-lost-found-medha` Vercel project, configure Production variables:

- `DATABASE_URL` — Neon PostgreSQL connection string.
- `JWT_SECRET_KEY` — random secret, at least 32 characters.
- `JWT_ALGORITHM` — normally `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES` — 1–15.
- `REFRESH_TOKEN_EXPIRE_DAYS` — positive integer.
- `APP_ENV=production`.
- `FRONTEND_ORIGIN` — deployed frontend origin only if cross-origin requests
  are used; same-origin Vercel routing does not require CORS.

Do not place backend secrets in frontend variables or Git. After the variables
are set, deploy the current source, verify the site and API, then make the
deployment publicly accessible by adjusting SSO protection if that is the
desired final access policy.

## 5. Final Screenshot Checklist

- [ ] User-side home/browse view with real lost/found reports.
- [ ] Admin dashboard with statistics, user management, and activity.
- [ ] RBAC-denied request showing the expected 403 response.
- [ ] Expired/invalid access-token request showing 401.
- [ ] Activity/audit log view and CSV export control.

Screenshots, demo accounts, and sample data are not fabricated or included by
this report.
