# AI Income Engine

An autonomous, multi-lane income system orchestrated by Claude AI. Azure Functions handle scheduling and execution; PostgreSQL tracks all state; the Claude API drives every decision loop.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Azure (cloud host)                          │
│                                                                     │
│  ┌──────────────┐     ┌───────────────────────────────────────────┐ │
│  │   Scheduler  │────▶│           Orchestrator Function           │ │
│  │ (Timer Trig) │     │  (Claude API — claude-opus-4-7 / sonnet)  │ │
│  └──────────────┘     └───────────┬───────────────────────────────┘ │
│                                   │ dispatches jobs                 │
│          ┌────────────────────────┼──────────────────────┐          │
│          ▼                        ▼                       ▼          │
│  ┌──────────────┐  ┌───────────────────────┐  ┌────────────────┐   │
│  │  Content     │  │  Marketplace / Leads  │  │  Finance       │   │
│  │  Lane Fn     │  │  Lane Fn              │  │  Lane Fn       │   │
│  └──────┬───────┘  └───────────┬───────────┘  └───────┬────────┘   │
│         │                      │                       │            │
│         └──────────────────────┼───────────────────────┘            │
│                                ▼                                    │
│                    ┌───────────────────────┐                        │
│                    │  PostgreSQL State DB   │                        │
│                    │  (Azure Database for   │                        │
│                    │   PostgreSQL Flex Srv) │                        │
│                    └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### Scheduler
- **Azure Timer Trigger Function** that fires on a configurable cron expression (default: every 15 min).
- Reads the `run_queue` table; skips lanes that are rate-limited or paused.
- Enqueues job payloads to Azure Storage Queue for fan-out.

### Claude API Orchestrator
- **Azure Queue-Trigger Function** (Python or Node) that consumes scheduler messages.
- Calls `claude-opus-4-7` (or `claude-sonnet-4-6` for lighter tasks) with a system prompt encoding the current lane's goal, constraints, and recent history fetched from PostgreSQL.
- Prompt caching is enabled on the system prompt block to minimize token cost.
- Returns a structured `Action` JSON that the lane function executes.
- Writes every decision + result back to the `run_log` table.

### PostgreSQL State Store
Managed via Alembic migrations. Core tables:

| Table | Purpose |
|---|---|
| `lanes` | One row per income lane — config, schedule, enabled flag |
| `run_queue` | Pending and in-flight job records |
| `run_log` | Append-only history of every orchestrator decision |
| `income_events` | Recorded revenue, lead, or asset events with amounts |
| `kv_store` | Arbitrary key-value state scoped per lane |

### Income Lanes

Each lane is an independent Azure Function triggered by the orchestrator.

| Lane | What it does |
|---|---|
| **Content** | Generates, schedules, and posts content (articles, threads, short-form video scripts) using Claude; tracks engagement metrics back to the DB. |
| **Marketplace / Leads** | Scans target platforms for opportunities, drafts outreach or listings, logs conversions to `income_events`. |
| **Finance** | Monitors account balances and surfaces rebalancing or billing optimizations; never executes trades autonomously without a human approval step. |

---

## Directory Layout (planned)

```
moneyman/
├── infra/                  # Terraform for Azure resources
│   └── main.tf
├── db/
│   ├── alembic.ini
│   └── migrations/
├── functions/
│   ├── scheduler/          # Timer trigger
│   ├── orchestrator/       # Queue trigger — Claude API calls
│   ├── lane_content/
│   ├── lane_marketplace/
│   └── lane_finance/
├── shared/
│   ├── db.py               # SQLAlchemy session factory
│   ├── claude_client.py    # Anthropic SDK wrapper w/ prompt caching
│   └── models.py           # SQLAlchemy ORM models
├── .env.example
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Compute | Azure Functions (Python 3.11 or Node 20, Flex Consumption plan) |
| AI | Anthropic Claude API — `claude-opus-4-7` / `claude-sonnet-4-6` |
| Database | Azure Database for PostgreSQL – Flexible Server |
| Queue | Azure Storage Queue (orchestrator fan-out) |
| Secrets | Azure Key Vault (referenced via managed identity) |
| IaC | Terraform |
| Migrations | Alembic (Python) |

---

## Getting Started

1. Copy `.env.example` → `.env` and fill in secrets.
2. `cd infra && terraform init && terraform apply` to provision Azure resources.
3. `cd db && alembic upgrade head` to apply migrations.
4. `func start` inside any `functions/` subdirectory for local development.

---

## Design Principles

- **Observe before you act.** Every lane reads current state from PostgreSQL before Claude generates an action; stale decisions are blocked by a freshness check.
- **Append-only audit log.** `run_log` is never updated, only inserted. Full replay is always possible.
- **Human gate on money moves.** The Finance lane surfaces recommendations; any action touching real funds requires an explicit approval record in `run_log`.
- **Cost-aware AI calls.** System prompts are cached; `sonnet-4-6` handles routine tasks; `opus-4-7` is reserved for strategy decisions.
