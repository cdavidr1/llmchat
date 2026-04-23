# llmchat

FastAPI skeleton for the Tribal LLM chat service.

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
cd /home/yamashi/Work/Python/Tribal/llmchat
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
/vault/secrets/database_url
/vault/secrets/allowed_tables
/vault/secrets/oracle.json
```

`allowed_tables` should contain a comma-separated list:

```text
customers,orders,products
```

The loader supports two secret formats:

- one setting per file in `/vault/secrets`
- the reference app's `/vault/secrets/oracle.json` with `url`, `username`, and
  `password`

Resolution order is:

1. Vault mounted files under `/vault/secrets`
2. Vault `oracle.json`
3. `/app/config.example`
4. built-in defaults

If both Vault formats are present, the one-setting-per-file values win for
overlapping keys. `config.example` only fills in missing values.

For local development, this repo includes `config.example/`. You can point the app to it with:

```bash
LLMCHAT_CONFIG_DIR=./config.example uvicorn app.main:app --reload
```

Environment variables are now only a bootstrap/fallback layer and use the `LLMCHAT_` prefix. For example:

```bash
LLMCHAT_CONFIG_DIR=/vault/secrets
SECRET_FILE=/vault/secrets/oracle.json
```

`allowed_tables` is intentionally explicit. The future LLM/database flow should only expose tables listed there.

To inspect what configuration shape was loaded without exposing secret values:

```bash
curl http://127.0.0.1:8000/config-source
```

## Chat Endpoint

The `/chat` endpoint is currently a placeholder. It validates config and requested table access, but it does not call LangChain yet.

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What orders were created today?","tables":["orders"]}'
```

## Database Tools

Before wiring any model provider, the service now exposes a small provider-agnostic
database tool layer. These tools are intentionally narrow and do not accept
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
- MCP
- provider-specific tool bindings

## Next Step

The LangChain integration should be added behind a service layer, not directly inside route handlers. That keeps HTTP concerns separate from LLM orchestration.
