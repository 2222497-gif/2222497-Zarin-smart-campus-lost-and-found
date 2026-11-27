# Campus Lost and Found

A campus lost-and-found application with a React/TypeScript frontend and a
FastAPI backend. It supports account sessions, reusable role/permission checks,
group-scoped item sharing, and an admin dashboard with audit export.

## Project layout

- `backend/` — FastAPI routes, SQLAlchemy models, authentication, RBAC, and tests.
- `frontend/` — React and TypeScript application built with Vite.
- `vercel.json` — routes `/api/*` to the backend service and other paths to the
  frontend service.

## Run locally

### Backend

Use Python 3.10 or newer and PostgreSQL. In PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` and `JWT_SECRET_KEY` in `backend/.env`; use a random secret
of at least 32 characters. Keep `.env` local and do not commit it. The example
uses `FRONTEND_ORIGIN=http://localhost:5173` and `APP_ENV=development`.

Start the API from `backend/`:

```powershell
fastapi dev main.py
```

The API is available at `http://localhost:8000`; interactive API docs are at
`http://localhost:8000/docs`.

### Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the local backend.
`VITE_API_URL` may be left blank when using that proxy or Vercel's same-origin
API rewrite. Set it only when the API is hosted at a separate base URL.

## Authorization behavior

- Access tokens are short-lived and tied to revocable, rotating server-side
  sessions.
- Admin routes use the shared permission dependency in `backend/rbac.py`.
- Ungrouped item reports remain public for compatibility with existing records.
- Group items are visible only to group owners and members. Members can view and
  create group items and edit/delete only their own. Owners can manage all group
  items, group settings, and membership.
- Removing a member or archiving a group does not delete or transfer item rows.
  Archived group items are no longer accessible through the application.
- Group membership and settings changes, plus item changes, are written to the
  audit log.

## Tests and build

Run backend tests from `backend/` with the project virtual environment active:

```powershell
python -m unittest discover -s tests -v
```

Build the frontend from `frontend/`:

```sh
npm run build
```

## Vercel deployment

Import the repository with the project root set to `./`. `vercel.json` configures
the frontend and backend services and routes `/api/*` to FastAPI. Leave
`VITE_API_URL` unset/blank for the same-origin rewrite.

Configure backend environment variables in Vercel, including:

- `DATABASE_URL`
- `JWT_SECRET_KEY` and `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES` and `REFRESH_TOKEN_EXPIRE_DAYS`
- `APP_ENV=production`
- `FRONTEND_ORIGIN` only when cross-origin browser access is needed; it accepts
  comma-separated deployed frontend origins. Localhost origins are excluded
  from production CORS.

If the frontend and API are deployed on different origins, set
`VITE_API_URL` to the API base URL and configure the exact frontend origin in
`FRONTEND_ORIGIN`. Never place backend secrets in frontend variables.

A production build can be checked with `npm run build` from `frontend/`. The
live Vercel deployment and its configured environment variables must still be
verified in the Vercel project before submission.
