# Tomorrow Viva and Demo Checklist

## Before the Viva

- Start the FastAPI backend from `backend/`.
- Start the Vite frontend from `frontend/`.
- Confirm `http://127.0.0.1:8000/api/health` returns `{"status":"ok"}`.
- Open `http://localhost:5173/` and verify the interface loads without console errors.
- Prepare at least one normal account and one administrator account.
- Prepare an owner account, a member account, and a non-member account for the
  group permission demonstration; add only test accounts to the group.
- Confirm the database contains realistic demo items.
- Open the browser Network and Application tabs before demonstrating login.

## Five-to-Eight-Minute Demo Sequence

1. Show the responsive homepage, real item records, search, and Lost/Found filter.
2. Log in with a normal user.
3. Open Account and update the profile.
4. Change the password and confirm the success response.
5. Report a lost or found item and show it appear in the item list.
6. Edit or delete only the item owned by the signed-in user.
7. Attempt an unauthorized item change or protected admin request in code or via another account.
8. Create a group as its owner, add the member, and report a group-scoped item.
9. Show that the member can see the shared item but a non-member cannot; show
   that a member cannot edit another member's item while the owner can.
10. Remove the member and show that their item remains stored but is no longer
    available to them.
11. Log in as an administrator.
12. Show real statistics, paginated user search/filter, role protection,
    ban/unban, login attempts, failed-login audit entries, and CSV export.
13. Explain JWT creation, verification, expiry, session revocation, and
    role/group authorization from the code.

## Code Defence Talking Points

### JWT

- `backend/auth.py` creates a signed JWT using `sub`, `role`, `sid`, `jti`, `iat`, and `exp`.
- `decode_access_token()` verifies the signature, algorithm, required claims, and expiry.
- `get_current_user()` decodes the bearer token and loads the database user.
- Protected endpoints use the authentication dependency.
- The access lifetime is configurable in the environment.
- Refresh tokens are rotated and stored as hashes; logout and session revocation invalidate the associated access token.

### Ownership

- Items store `user_id`.
- Ungrouped update/delete checks compare the item owner with the authenticated
  user; administrators follow the existing ungrouped item permission.
- Group items additionally check active group membership. Members can change
  only their own group items; the group owner can change any item in that group.
- Frontend ownership controls do not replace server-side authorization.

### RBAC

- The database stores `role`.
- `/api/me` requires authentication.
- Admin endpoints use the reusable `get_admin_user()` permission dependency from `backend/rbac.py`.
- Item updates/deletes use the shared owner-or-admin authorization check.
- Group permissions are fixed: owners manage group settings, membership, and all
  group items; members view/create group items and manage only their own.
- Group removal/archive does not delete or transfer item rows.
- The frontend uses `currentUser.role` only to control menu visibility.
- Server dependencies remain responsible for authorization.

### Safety Rules

- An administrator cannot ban themselves.
- An administrator cannot remove their own administrator role.
- A banned user is rejected by `get_current_user()` on protected requests.

## Known Unverified Items

- The backend test suite and frontend production build pass; still verify the
  complete UI flows in a browser.
- Configure and verify the live Vercel deployment, production environment
  variables, and database connection.
- Prepare demo accounts and sample data in the designated demo database. This
  repository change did not create accounts or populate production data.
- Capture required screenshots and record the submission demonstration.

## Documentation

Keep this checklist, the README, environment examples, API routes, test evidence, screenshots, and final report synchronized throughout implementation.
