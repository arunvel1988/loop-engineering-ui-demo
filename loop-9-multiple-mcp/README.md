# Groq + Multiple MCP Servers DevOps Incident Response Lab

This Docker Compose lab uses a Groq-hosted model and **five independent MCP servers**:
- monitoring-mcp
- logs-mcp
- deployment-mcp
- container-mcp
- remediation-mcp

It uses synthetic monitoring/deployment evidence and a demo-only rollback endpoint. It does not mount the Docker socket or run host commands.

## Requirements
- Docker Engine and Docker Compose plugin
- Groq API key

## Run
```bash
cp .env.example .env
# edit .env and set GROQ_API_KEY
docker compose up --build -d
docker compose ps
```

Open:
- Agent API docs: http://localhost:8080/docs
- Demo application: http://localhost:5000/
- Agent tools: http://localhost:8080/tools

## Demo flow
1. Trigger incident: `curl -X POST http://localhost:8080/simulate-incident`
2. Investigate: `curl -X POST http://localhost:8080/incident -H 'Content-Type: application/json' -d '{"alert":"Demo application degraded and simulated CPU at 92%"}'`
3. In the report, find the remediation proposal ID (the agent should call `propose_fix` and report the returned ID).
4. Approve only after reviewing the report:
```bash
curl -X POST http://localhost:8080/approve \
  -H 'Content-Type: application/json' \
  -d '{"proposal_id":"REPLACE_WITH_ID","approved":true}'
```
5. Verify: `curl http://localhost:5000/health`

Reject a proposal with `approved:false`.

## Important lab notes
- `monitoring-mcp` and `container-mcp` expose simulated metrics/process usage for safe reproducibility.
- Deployment history is synthetic. Logs MCP reads `/logs/app.log`.
- The app's incident state is shared through a Docker volume. Remediation only calls the demo app's `/rollback` endpoint.
- MCP server access is internal to the Compose network; only the agent and demo app ports are published.
- This is a teaching demo, not production-ready. Add authentication, durable approvals, audit logging, retries/timeouts, and robust schema validation before real use.
