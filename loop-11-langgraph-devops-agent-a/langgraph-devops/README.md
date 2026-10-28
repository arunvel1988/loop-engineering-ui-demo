# LangGraph DevOps Incident Agent — Docker Compose Lab

## Architecture

Flask dashboard :8081 -> FastAPI agent :8080 -> LangGraph graph -> read-only MCP servers -> simulated app :5000.

Graph: START -> collect_evidence -> analyze (Groq) -> conditional branch -> prepare_proposal/no_action -> render_report -> END.

Five MCP services: monitoring, logs, deployment, container, remediation. The investigation graph **never invokes remediation tools**. Only the separate, authenticated `/approve` demo endpoint invokes the remediation server. Demo restoration is limited to resetting the simulated app to healthy state.

## Quick start

```bash
cp .env.example .env
# Edit .env: set your Groq API key and a long random approval secret
# For a random secret: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
docker compose up --build -d
docker compose ps
docker compose logs -f agent
```

Open `http://localhost:8081` for the Flask dashboard. Agent OpenAPI docs: `http://localhost:8080/docs`. Simulated app: `http://localhost:5000/health`.

### Exercise

1. Choose any scenario from the dashboard dropdown and click Simulate incident.
2. Click Run LangGraph investigation.
3. Inspect the diagnosis, tool trace, and proposed action (when one is justified).
4. Approve or reject explicitly. The only supported demo remediation resets the simulated app to healthy state; it does not modify a real system.
5. Click Run evaluation suite for 17 read-only scenarios. The evaluator resets state between cases.

### Scenario catalog

- `healthy`: normal baseline.
- `bad_deployment`: new version correlated with checkout errors.
- `cpu_spike`: CPU saturation.
- `database_failure`: database connection refused.
- `memory_pressure`: memory exhaustion.
- `network_latency`: upstream latency and 504s.
- `disk_pressure`: disk nearly full and write failures.
- `dependency_timeout`: payment gateway timeout.
- `config_drift`: unsafe configuration drift.
- `traffic_spike`: request surge and queue growth.
- `auth_failure`: elevated authentication failures.
- `container_crashloop`: repeated restarts/readiness failures.
- `queue_backlog`: background queue backlog.
- `certificate_expiry`: TLS certificate near expiry.
- `rate_limit`: high HTTP 429/throttling volume.
- `stale_alert`: stale alert with healthy current telemetry (false-positive control).
- `intermittent_errors`: sporadic 502s and elevated latency.

All scenarios are synthetic state fixtures. The current graph collects seven read-only MCP evidence sources and uses deterministic server-side thresholds to classify healthy vs incident before asking Groq for a narrative diagnosis. The proposal gate remains deliberately narrow: only the synthetic `bad_deployment` fixture can create the demo restore proposal.

### CLI example

```bash
curl -s -X POST http://localhost:5000/simulate -H 'Content-Type: application/json' -d '{"scenario":"bad_deployment"}'
curl -s -X POST http://localhost:8080/incident -H 'Content-Type: application/json' -d '{"alert":"Checkout 503 after deployment"}' | python3 -m json.tool
```

## Safety and limitations

- This is a **teaching lab**, not a production-ready incident management system. No real Kubernetes, Docker, AWS or Linux host is modified.
- In evaluation mode, no proposal is generated; all graph MCP calls are from a fixed read-only allowlist.
- The demo approval secret is a shared credential between the Flask dashboard, agent and remediation server. Use a separate authorization service with authenticated user identity, role-based authorization, durable one-time approvals, audit logging, expiry, and transaction-safe persistence before any real production remediation.
- Proposals are in-memory and disappear on restart. Single agent process only; not safe for multiple replicas.
- The demo ports are published for local use. Bind them to loopback or firewall them when on a public VM. For example change `8081:8081` to `127.0.0.1:8081:8081`.
- Groq receives the simulated incident evidence. For real systems, assess data sensitivity and organizational policy before sending logs or metrics externally.
- The production compose file is an **illustrative read-only scaffold** and has no live MCP implementations. Do not connect it to a writable MCP server; verify tool permissions and service identities independently.
- Seventeen evaluation cases are learning/smoke tests, not sufficient production coverage. Extend with missing-tool, malicious-tool-output, timeouts, injection, stale evidence, approval replay, concurrency, authorization and recovery tests.
- `/simulate`, `/reset`, `/internal/restore` are demo-only endpoints. Never expose these on production infrastructure.
- No persistence/checkpointer is configured for LangGraph; the graph is invoked fresh for each incident. Add durable checkpointing and correlation IDs for long-running investigations.

## Test syntax

```bash
python3 -m compileall -q agent mcp demo dashboard
python3 -m json.tool dashboard/evaluation_cases.json >/dev/null
```
