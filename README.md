# Airline Disruption Resolution Agent

An AI-powered customer support agent for airline disruption scenarios (cancellations, delays).
Built with **LangGraph**, **Gemini 2.5 Flash**, **FastAPI**, and **SQLite**.

## Quick Start

### 1. Set your API key

Edit the `.env` file (already created):

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Install dependencies

```powershell
$env:Path = "C:\Users\CENTER LAB 2\.local\bin;$env:Path"
uv sync
```

### 3. Run the server

```powershell
uv run uvicorn aionos_assignment.api.main:app --reload
```

The server auto-seeds the database on first startup.

- **Chat UI:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## Run Mock Tests (no API key needed)

```powershell
uv run python -m aionos_assignment.tests.test_mock_flow
```

---

## Project Structure

```
src/aionos_assignment/
  api/          - FastAPI routes and schemas
  db/           - SQLAlchemy models, database engine, seed script
  graph/        - LangGraph state and workflow
  policies/     - Service rules (cancellation, delay, refund, escalation)
  utils/        - Session memory utilities
  tests/        - Mock tests
templates/
  index.html    - HTML chat UI
.env            - Your API keys (fill in before running)
plan.md         - Full project plan and architecture
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | HTML chat UI |
| POST | `/chat/start` | Start a new session |
| POST | `/chat` | Send message, get response |
| GET | `/session/{id}` | Get conversation history |
| GET | `/session/{id}/actions` | Get actions for session |
| DELETE | `/session/{id}` | Close session |
| GET | `/admin/customers` | List all customers |
| GET | `/admin/actions` | List all agent actions |
| GET | `/health` | Health check |

---

## Test Scenarios

| Customer | PNR | Situation |
|----------|-----|-----------|
| Priya Nair (Gold) | SK4821X | Flight cancelled — offer refund/rebook, escalate upgrade |
| Arvind Kulkarni (Silver) | TR1190B | 4h delay — meal + lounge, explain no hotel |
| Meher Kaur (Platinum) | WL7742 | 6h delay — meal + hotel, escalate full-night + fare waiver |
