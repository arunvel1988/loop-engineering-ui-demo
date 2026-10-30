# LangGraph Multi-Agent DevOps Incident Lab

Docker Compose lab: Flask UI, simulated checkout app, LangGraph specialist agents, five MCP services, Groq, explicit approval for **simulated-only** remediation, and 17 fixture evaluations.

## Workflow
Monitoring Specialist -> Log Analysis Specialist -> Deployment Specialist -> Container Specialist -> Incident Commander -> conditional incident/healthy report -> Safety Reviewer.

MCP servers expose monitoring metrics/alerts, logs/search, deployment/config history, container status/process descriptions, and a proposal-only remediation service. The app does not inspect real processes or infrastructure.

## Scenarios
healthy, stale_alert, bad_deployment, cpu_spike, memory_pressure, disk_pressure, container_crashloop, database_failure, network_latency, dependency_timeout, intermittent_errors, config_drift, traffic_spike, queue_backlog, rate_limit, auth_failure, certificate_expiry.

## Run
```bash
cp .env.example .env
```
Edit `.env` and set `GROQ_API_KEY`, `GROQ_MODEL` and a strong `APPROVAL_SECRET`. Generate a secret with:
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```
Build:
```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 agent
```
Open `http://YOUR_VM_IP:8081` from a trusted network. Restrict ports with a firewall or use an SSH tunnel; do not expose the dashboard publicly.

## Use
1. Select a scenario.
2. Click Simulate incident.
3. Click Run multi-agent investigation.
4. Review diagnosis, metrics, specialist findings, evidence, safety note and raw trace.
5. Incident findings create a proposal only. Approve/reject it to exercise simulator-only remediation.
6. Run all 17 fixture evaluations; the simulator resets to healthy after the suite.

## Troubleshooting
```bash
docker compose ps
docker compose logs --tail=150 agent
docker compose logs --tail=100 monitoring-mcp logs-mcp deployment-mcp container-mcp remediation-mcp
docker compose logs --tail=100 dashboard demo-app
```
If Groq falls back, check `.env` model/key, then `docker compose up -d --build agent`.

This project intentionally uses `mcp_servers/` for application code and does not have a local package directory named `mcp`, avoiding conflicts with the installed MCP SDK.

## Safety
All incident data is simulated. Remediation only edits the shared simulator state; it does not change real infrastructure. The approval secret is a demo guardrail, not production identity/authorization. Do not connect this writable remediation service to production.
