# Agentic DevOps Incident Lab — Flask Dashboard + Groq + MCP

A teaching/demo lab with a browser dashboard so you do **not** need to repeatedly run `curl` commands. It includes a simulated Flask application, five MCP servers, a Groq-powered FastAPI agent, and a separate Flask control-room UI.

## What you get

- **Dashboard:** `http://localhost:8081` — simulate incident, run AI investigation, approve/reject remediation, refresh health and view the report.
- **Demo app:** `http://localhost:5000` — synthetic app with `/health`, `/state`, `/logs` and `/simulate-incident` endpoints.
- **Agent API docs:** `http://localhost:8080/docs` — available for debugging, not needed for the normal demo.
- **MCP services:** monitoring, logs, deployment, container and remediation.
- **Safety:** investigation is read-only; remediation is an allowlisted demo rollback and requires explicit human approval. The lab does not mount the Docker socket or run arbitrary host commands.

The CPU value and deployment history are simulated teaching fixtures, not real host metrics.

## 1. Prerequisites

- Docker Engine and Docker Compose plugin
- A Groq API key
- Ports 5000, 8080 and 8081 available

## 2. Configure the Groq API key

From this directory:

```bash
cp .env.example .env
nano .env
```

Set `GROQ_API_KEY` to your own key. Do not commit `.env` to Git.

## 3. Start the full stack

```bash
docker compose up --build -d
docker compose ps -a
```

Open this in your browser:

**http://localhost:8081**

If the browser is on another computer, use `http://YOUR_VM_PUBLIC_IP:8081` and configure the VM firewall to allow the port only from your IP. Do not expose the agent API or demo endpoints publicly without appropriate network controls.

## 4. Run the incident demo from the UI

1. Open the dashboard.
2. Click **Simulate incident + investigate with AI**.
3. Wait for Groq to gather evidence from MCP tools and return its report.
4. Review the report and proposal ID.
5. Click **Approve demo rollback** or **Reject proposal**.
6. The dashboard refreshes health and shows the post-remediation status.

Other controls are available if you want to demonstrate individual steps: **Simulate incident only**, **Investigate current state**, and **Refresh status**.

## 5. Useful troubleshooting commands

These are only for troubleshooting; the dashboard handles the normal workflow.

```bash
docker compose ps -a
docker compose logs --tail 100 agent
docker compose logs --tail 100 dashboard
docker compose logs --tail 100 remediation-mcp
```

If dependencies change, rebuild cleanly:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## 6. Ports

| Service | Host port | Purpose |
|---|---:|---|
| Flask dashboard | 8081 | Main interactive UI |
| Demo application | 5000 | Simulated application and health endpoint |
| Agent API | 8080 | FastAPI and `/docs` |

## 7. Important limits

- This is a local teaching simulation. The monitoring CPU samples are synthetic.
- The remediation MCP allows only predefined demo actions. The rollback resets the demo application's stored state; it does not roll back a real deployment.
- The agent's report is an AI-generated hypothesis and must be checked against evidence.
- Before using a similar pattern for real infrastructure, add authentication, TLS, restricted ingress, durable proposal storage, audit logs, secret rotation, deployment environments and a separately enforced approval policy.


## Human approval from the dashboard

After clicking **Simulate incident + investigate with AI**, the dashboard displays the incident report and a **Remediation awaiting approval** panel when the remediation MCP creates a proposal. Use **Approve demo rollback** or **Reject proposal** directly in the dashboard; no curl command is needed. The agent returns the proposal ID as structured JSON from the MCP tool result, so the UI does not depend on the model writing the ID in a particular format.
