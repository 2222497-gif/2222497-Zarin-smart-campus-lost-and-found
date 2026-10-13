# Technical Design Document (TDD)

## 1. Tech Stack
- **Frontend**: React + TypeScript
- **Backend**: FastAPI + Python
- **Database**: SQLite / PostgreSQL

## 2. API Endpoints (MVP)
- `GET /api/items`: Retrieve list of all lost/found items.
- `POST /api/items`: Create a new lost/found item entry.
- `GET /api/items/{id}`: Get details of a specific item.
- `PUT /api/items/{id}`: Update an item entry.
- `DELETE /api/items/{id}`: Delete an item entry.

## 3. Data Model (Item Schema)
- `id`: integer (Primary Key)
- `title`: string
- `description`: string
- `category`: string (Lost / Found)
- `location`: string
- `contact_info`: string
- `created_at`: timestamp
