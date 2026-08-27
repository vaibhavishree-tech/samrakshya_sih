# Sāmarakṣya: Orchestration Layer

This repository contains pahse 3 -Agentic Orchestration Layer and phase 4- Knowledge and RAG layer for the Sāmarakṣya OSINT Command Center.

---

## Project Structure

```text

.
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── core_agents.py         # Agno agent declarations (Extraction, Verification, Link Analysis, Alerting)
│   │   ├── schemas.py             # Pydantic models for structured agent outputs
│   │   └── supervisor.py          # Pipeline orchestration, scoring math, and DB state handler
│   ├── core/
│   │   ├── config.py              # System settings and environment variable configurations
│   │   ├── database.py            # Async SQLAlchemy engine and session creation setup
│   │   └── models.py              # PostgreSQL database schemas (ThreatState, NetworkEdge)
│   └── rag/
│       ├── __init__.py
│       ├── seed_data.py            # Initial historical threat dataset for vector database startup
│       ├── tools.py                # Custom tool for agents to query vector search
│       └── vector_store.py         # Vector store logic and pgvector similarity search setup
├── main.py                         # FastAPI application entry point, app lifecycle, and API endpoints
├── .env
├── README.md
└── requirements.txt

```

---

### Local Setup & Installation

1. Environment Variables

Create a `.env` file in the root directory.

```python
PROJECT_NAME="सामरक्ष्य (Sāmarakṣya) OSINT Engine"
API_V1_STR="/api/v1"
GROQ_API_KEY="your_api_key_here"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
```

2. Database Container Initialization

Ensure Docker Desktop is running, then spin up the PostgreSQL container equipped with the `pgvector` extension:

```python
docker run -d --name samrakshya-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 ankane/pgvector
```

3. Apply Schema Patch

Execute this command once to append the missing timestamp column to the topology table:

```python
docker exec -it samrakshya-pg psql -U postgres -d postgres -c "ALTER TABLE network_edges ADD COLUMN interaction_timestamp TIMESTAMP WITHOUT TIME ZONE;"
```

4. Install Dependencies & Run

```python
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Note: On the first startup, the FastAPI lifespan event will automatically create the required database tables and seed the historical threat intelligence vectors.

---

### API Integration Contracts- Important for integration

These endpoints are the designated handoff points for the Ingestion Team and the Dashboard/Summarization Team.

| **Endpoint**         | **Method** | **Trigger**            | **Payload / Action**                                                                                                            |
| -------------------- | ---------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `/api/v1/analyze`    | `POST`     | **Ingestion Layer**    | **Expects:** `{"raw_text": "str", "document_id": "uuid (opt)"}`. Runs the 4-agent pipeline and writes a `READY` row to the DB.  |
| `/api/v1/synthesize` | `POST`     | **UI / Summarization** | **Expects:** Empty body. Queries the oldest `READY` threat, executes the Summarization Agent, and updates state to `COMPLETED`. |
| `/api/v1/rag/search` | `GET`      | **Diagnostic**         | **Expects:** `?query=keyword`. Directly queries the vector database to test semantic search boundaries.                         |

---

### `/api/v1/analyze` Output Value Breakdown

- status: The FastAPI endpoint executed the workflow without any server or parsing errors.

- threat_state_id: The unique UUID generated for this specific event in your PostgreSQL `threat_state` table.

- risk_score: The final threat severity out of 100.

- velocity_detected: Explicitly indicates whether the pipeline found evidence of rapid, timestamped sharing, such as a coordinated bot swarm

- extracted_entities_count: This represents the total number of distinct items (like user handles, hashtags, or locations) that the Extraction Agent successfully isolated from the raw text.

- edges_mapped: This indicates the number of active interactions (such as a 'SHARE' or 'MENTION') the Link Analysis Agent found connecting those extracted entities together.

---

### The Agent Workflow

- Extraction Agent: Isolates handles, hashtags, organizations, and locations, flagging suspicious entities based on behavioral context.

- Verification Agent: Uses the `retrieve_threat_context` RAG tool to cross-reference suspicious entities against the PostgreSQL vector store, identifying known threat campaigns.

- Link Analysis Agent: Maps semantic topologies (e.g., SHARE, MENTION) between actors and targets, capturing complex operational networks.

- Supervisor Scoring: Computes a rigid mathematical baseline score based on entity volume, edge density, and verified RAG matches.

- Alerting Agent: Assesses the mathematical baseline alongside contextual velocity, outputting the final `risk_score` (0-100).

---

### Database State Management

The supervisor manages state across two primary PostgreSQL tables accessed via SQLAlchemy:

- `threat_state`: Stores the event UUID, raw OSINT text, parsed JSON entities, baseline reasoning, final risk score, and the pipeline status (`READY` -> `COMPLETED`).

- `network_edges`: Stores structural relationships linking a `source_node` to a `target_node`. It explicitly captures the `interaction_type` (e.g., "SHARE", "MENTION") so the frontend UI can accurately label and color-code the connection lines on the interactive threat graph.