# llmchat

FastAPI skeleton for the LLM chat service..

## What Is Here

- `app/main.py` creates the FastAPI application.
- `app/api/routes.py` contains HTTP endpoints.
- `app/core/config.py` centralizes environment-based settings.
- `app/repositories/database.py` owns database access rules.
- `app/services/database_service.py` owns database-related application logic.
- `app/services/chat_service.py` owns chat orchestration.
- `tests/test_health.py` verifies the service starts and responds.

## Run Locally

```bash
cd /llmchat
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## Test

```bash
pytest
```

## Git Hooks

This repo includes a tracked pre-commit hook in `.githooks/pre-commit` that
runs Gitleaks through Docker before Git accepts a commit.

Enable it once per clone with:

```bash
./scripts/install-git-hooks.sh
```

## Kubernetes

Kubernetes manifests live in `k8s/` and follow the Vault Agent Injector pattern
from the generated Vault demo app.

Build the local image expected by the deployment with:

```bash
docker build -t python-vault-app:local .
```

The deployment currently mirrors the reference app and expects a Vault role
named `oracle-app` with a KV v2 secret at:

```text
apps/data/db/oracle
```

For the reference-compatible `oracle.json` path, that secret should contain:

```text
url
username
password
```

Apply the manifests with:

```bash
kubectl apply -f ./k8s
```

Port-forward the service with:

```bash
kubectl port-forward -n vault-demo svc/python-vault-app 8000:8000
```

Then open:

```text
http://127.0.0.1:8000/health
```

## Configuration

Configuration is designed for a vault sidecar/security proxy approach.

The app does not talk to Vault directly. Instead, Vault Agent Injector fetches
configuration from Vault and writes it into `/vault/secrets`. The FastAPI app
tries to load injected secret data first, then fills any missing settings from
`/app/config.example` if it exists, and only then falls back to built-in
defaults.

Expected mounted files:

```bash
/vault/secrets/app_name
/vault/secrets/app_env
/vault/secrets/log_level
/vault/secrets/llm_provider
/vault/secrets/llm_model
/vault/secrets/llm_provider_api_key
/vault/secrets/ollama_base_url
/vault/secrets/mcp_server_url
```

The loader expects one setting per file in `/vault/secrets`. A legacy
`oracle.json` file is detected for config-source reporting, but database
credentials are owned by the external MCP DB server.

Resolution order is:

1. Vault mounted files under `/vault/secrets`
2. `/app/config.example`
3. built-in defaults

`config.example` only fills in missing values.

For local development, this repo includes `config.example/`. You can point the app to it with:

```bash
LLMCHAT_CONFIG_DIR=./config.example uvicorn app.main:app --reload
```

Environment variables are now only a bootstrap/fallback layer and use the `LLMCHAT_` prefix. For example:

```bash
LLMCHAT_CONFIG_DIR=/vault/secrets
SECRET_FILE=/vault/secrets/oracle.json
```

To inspect what configuration shape was loaded without exposing secret values:

```bash
curl http://127.0.0.1:8000/config-source
```

## Chat Providers

Provider selection now lives behind a small factory and adapter layer:

- `openai` uses the OpenAI Python SDK and the Responses API
- `ollama` uses the Ollama Python SDK and local `/api/chat` tool calling

The database tool layer stays provider-agnostic.

For local development, `config.example/` now defaults to Ollama:

```text
llm_provider=ollama
llm_model=qwen3
ollama_base_url=http://host.docker.internal:11434
mcp_server_url=http://host.docker.internal:8001/mcp
```

If you run the app outside Docker, override the base URL if needed:

```bash
LLMCHAT_OLLAMA_BASE_URL=http://localhost:11434
```

Make sure Ollama is running and the model exists locally, for example:

```bash
ollama pull qwen3
```

To switch back to OpenAI later, set:

```text
llm_provider=openai
llm_model=gpt-4o-mini
llm_provider_api_key=<your-api-key>
```

## Chat Endpoint

The `/chat` endpoint validates requested table access, creates or resumes an
in-memory session, and uses the configured provider when that provider is
configured.
When `llm_provider` is `openai` or `ollama`, it calls the configured provider
through a provider adapter. The adapter calls the external MCP DB server for
database tools instead of executing local DB tools in-process.

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What orders were created today?","tables":["orders"]}'
```

To continue a conversation, pass the returned `session_id`:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"returned-session-id","message":"Which customer placed the first one?","tables":["orders","customers"]}'
```

For OpenAI, set `llm_provider_api_key` through Vault mounted files,
`config.example`, or the `LLMCHAT_LLM_PROVIDER_API_KEY` environment variable.
The placeholder value `replace-me` is treated as not configured.

## Database Tools

The service now calls the external MCP DB server for database tools. The tool
contract still exposes the same narrow read-only operations and does not allow
arbitrary SQL.

Available tools:

- `list_allowed_tables`
- `describe_table`
- `query_table`

REST endpoints for manual testing:

```bash
curl http://127.0.0.1:8000/tools
curl http://127.0.0.1:8000/tools/tables
curl http://127.0.0.1:8000/tools/tables/customers
curl -X POST http://127.0.0.1:8000/tools/query \
  -H 'Content-Type: application/json' \
  -d '{"table_name":"customers","columns":["name"],"limit":5}'
```

The tool layer currently supports:

- listing the explicitly allowed tables
- describing columns on one allowed table
- reading a bounded number of rows from one allowed table

It does not yet support:

- free-form SQL
