from flask import (
    Flask,
    render_template,
    request,
    jsonify
)

from agent import run_agent

from tools import (
    terminate_process,
    check_server,
    check_processes
)

import threading


app = Flask(__name__)


# =========================================================
# PENDING ACTIONS
# =========================================================

pending_actions = {}


# =========================================================
# INCIDENTS
# =========================================================

incidents = {}

incident_counter = 0


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# CHAT
# =========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json()

        message = data.get(
            "message",
            ""
        ).strip()


        if not message:

            return jsonify({

                "error":
                    "Message cannot be empty."

            }), 400


        # -------------------------------------------------
        # Run Agent
        # -------------------------------------------------

        result = run_agent(
            message
        )


        # -------------------------------------------------
        # Check pending remediation
        # -------------------------------------------------

        pending_action = (
            result.get(
                "pending_action"
            )
        )


        if pending_action:

            pid = pending_action[
                "arguments"
            ]["pid"]


            action_id = str(
                pid
            )


            pending_actions[
                action_id
            ] = pending_action


            result[
                "action_id"
            ] = action_id


        return jsonify(
            result
        )


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# =========================================================
# AUTOMATIC INCIDENT INVESTIGATION
# =========================================================

def investigate_incident(
    incident_id,
    incident
):

    print()
    print(
        "=================================================="
    )
    print(
        "STARTING AUTOMATIC INCIDENT INVESTIGATION"
    )
    print(
        "=================================================="
    )

    print(
        "Incident:",
        incident_id
    )

    print(
        "Alert:",
        incident.get(
            "alertname"
        )
    )


    # -----------------------------------------------------
    # Update incident status
    # -----------------------------------------------------

    incident["agent_status"] = (
        "investigating"
    )


    incident["agent_message"] = (
        "DevOps Agent is investigating this incident."
    )


    try:

        # -------------------------------------------------
        # Build investigation task
        # -------------------------------------------------

        task = f"""
A production infrastructure incident has been automatically detected.

Incident ID:
{incident_id}

Alert:
{incident.get("alertname", "Unknown")}

Severity:
{incident.get("severity", "Unknown")}

Instance:
{incident.get("instance", "Unknown")}

Summary:
{incident.get("summary", "")}

Description:
{incident.get("description", "")}

The incident was generated automatically by Alertmanager.

Investigate this incident using the available infrastructure
observation tools.

Do not assume the root cause.

Collect real telemetry and correlate the evidence.

Identify the root cause only when the evidence supports it.

If a remediation is justified, propose it using the available
remediation mechanism.

Do not invent infrastructure information.

After investigation, provide:

Investigation Summary

Root Cause

Evidence

Recommended Remediation

Risk Assessment

Action Required
"""


        print()
        print(
            "Sending incident to GPT-OSS..."
        )


        # -------------------------------------------------
        # RUN EXISTING AGENT
        # -------------------------------------------------

        result = run_agent(
            task
        )


        # -------------------------------------------------
        # Store agent response
        # -------------------------------------------------

        incident["agent_status"] = (
            "completed"
        )


        incident["agent_response"] = (
            result.get(
                "response",
                ""
            )
        )


        # -------------------------------------------------
        # Check remediation request
        # -------------------------------------------------

        pending_action = (
            result.get(
                "pending_action"
            )
        )


        if pending_action:

            pid = pending_action[
                "arguments"
            ].get(
                "pid"
            )


            action_id = (
                f"{incident_id}-{pid}"
            )


            pending_actions[
                action_id
            ] = pending_action


            incident["action_id"] = (
                action_id
            )


            incident["pending_action"] = (
                pending_action
            )


            incident["agent_status"] = (
                "waiting_for_approval"
            )


            incident["agent_message"] = (
                "The DevOps Agent identified a "
                "remediation action. Human approval "
                "is required."
            )


        else:

            incident["agent_message"] = (
                "Investigation completed."
            )


        print()
        print(
            "=================================================="
        )

        print(
            "INCIDENT INVESTIGATION COMPLETED"
        )

        print(
            "Incident:",
            incident_id
        )

        print(
            "Agent Status:",
            incident["agent_status"]
        )

        print(
            "=================================================="
        )


    except Exception as e:

        # -------------------------------------------------
        # Investigation failed
        # -------------------------------------------------

        incident["agent_status"] = (
            "failed"
        )


        incident["agent_message"] = (
            "Automatic investigation failed."
        )


        incident["agent_error"] = (
            str(e)
        )


        print()
        print(
            "=================================================="
        )

        print(
            "INCIDENT INVESTIGATION FAILED"
        )

        print(
            "Incident:",
            incident_id
        )

        print(
            "Error:",
            str(e)
        )

        print(
            "=================================================="
        )


# =========================================================
# ALERTMANAGER WEBHOOK
# =========================================================

@app.route(
    "/webhook/alert",
    methods=["POST"]
)
def alert_webhook():

    global incident_counter

    try:

        # -------------------------------------------------
        # Receive Alertmanager payload
        # -------------------------------------------------

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success":
                    False,

                "error":
                    "Empty or invalid JSON payload."

            }), 400


        print()
        print(
            "=================================================="
        )

        print(
            "ALERT RECEIVED FROM ALERTMANAGER"
        )

        print(
            "=================================================="
        )


        # -------------------------------------------------
        # Alertmanager sends an "alerts" array
        # -------------------------------------------------

        alerts = data.get(
            "alerts",
            []
        )


        created_incidents = []


        # -------------------------------------------------
        # Process every alert
        # -------------------------------------------------

        for alert in alerts:

            status = alert.get(
                "status",
                "unknown"
            )


            labels = alert.get(
                "labels",
                {}
            )


            annotations = alert.get(
                "annotations",
                {}
            )


            alertname = labels.get(
                "alertname",
                "UnknownAlert"
            )


            severity = labels.get(
                "severity",
                "unknown"
            )


            instance = labels.get(
                "instance",
                "unknown"
            )


            summary = annotations.get(
                "summary",
                alertname
            )


            description = annotations.get(
                "description",
                ""
            )


            # -------------------------------------------------
            # Generate Incident ID
            # -------------------------------------------------

            incident_counter += 1


            incident_id = (
                f"INC-{incident_counter:04d}"
            )


            # -------------------------------------------------
            # Create Incident
            # -------------------------------------------------

            incident = {

                "id":
                    incident_id,

                "alertname":
                    alertname,

                "status":
                    status,

                "severity":
                    severity,

                "instance":
                    instance,

                "summary":
                    summary,

                "description":
                    description,

                "started_at":
                    alert.get(
                        "startsAt"
                    ),

                "ended_at":
                    alert.get(
                        "endsAt"
                    ),

                "agent_status":
                    "queued",

                "agent_message":
                    "Incident received. "
                    "Investigation is starting.",

                "agent_response":
                    "",

                "raw_alert":
                    alert

            }


            # -------------------------------------------------
            # Store Incident
            # -------------------------------------------------

            incidents[
                incident_id
            ] = incident


            created_incidents.append(
                incident
            )


            print()
            print(
                "INCIDENT CREATED"
            )

            print(
                "Incident ID:",
                incident_id
            )

            print(
                "Alert:",
                alertname
            )

            print(
                "Severity:",
                severity
            )

            print(
                "Instance:",
                instance
            )


            # -------------------------------------------------
            # AUTOMATICALLY START AGENT
            # -------------------------------------------------

            investigation_thread = (
                threading.Thread(
                    target=investigate_incident,
                    args=(
                        incident_id,
                        incident
                    ),
                    daemon=True
                )
            )


            investigation_thread.start()


        print()
        print(
            "=================================================="
        )


        # -------------------------------------------------
        # Immediately respond to Alertmanager
        # -------------------------------------------------

        return jsonify({

            "success":
                True,

            "message":
                "Alert received and investigation started.",

            "incidents":
                created_incidents

        }), 200


    except Exception as e:

        print(
            "ERROR PROCESSING ALERT:"
        )

        print(
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# GET INCIDENTS
# =========================================================

@app.route(
    "/incidents",
    methods=["GET"]
)
def get_incidents():

    try:

        return jsonify({

            "success":
                True,

            "incidents":
                list(
                    incidents.values()
                )

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# GET SINGLE INCIDENT
# =========================================================

@app.route(
    "/incidents/<incident_id>",
    methods=["GET"]
)
def get_incident(
    incident_id
):

    incident = incidents.get(
        incident_id
    )


    if not incident:

        return jsonify({

            "success":
                False,

            "error":
                "Incident not found."

        }), 404


    return jsonify({

        "success":
            True,

        "incident":
            incident

    })


# =========================================================
# APPROVE REMEDIATION
# =========================================================

@app.route(
    "/approve",
    methods=["POST"]
)
def approve():

    try:

        data = request.get_json()


        action_id = str(
            data.get(
                "action_id"
            )
        )


        # -------------------------------------------------
        # Find pending action
        # -------------------------------------------------

        action = pending_actions.get(
            action_id
        )


        if not action:

            return jsonify({

                "success":
                    False,

                "error":
                    "Approval request not found "
                    "or already processed."

            }), 404


        # -------------------------------------------------
        # Validate action
        # -------------------------------------------------

        if action["tool"] != (
            "terminate_process"
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Unknown remediation action."

            }), 400


        pid = action[
            "arguments"
        ]["pid"]


        # -------------------------------------------------
        # Execute
        # -------------------------------------------------

        result = terminate_process(
            pid
        )


        # -------------------------------------------------
        # Remove pending action
        # -------------------------------------------------

        pending_actions.pop(
            action_id,
            None
        )


        # -------------------------------------------------
        # Verification
        # -------------------------------------------------

        server_after = check_server()

        processes_after = check_processes()


        return jsonify({

            "success":
                result.get(
                    "success",
                    False
                ),

            "action":
                action,

            "result":
                result,

            "verification": {

                "server":
                    server_after,

                "processes":
                    processes_after

            }

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# REJECT REMEDIATION
# =========================================================

@app.route(
    "/reject",
    methods=["POST"]
)
def reject():

    try:

        data = request.get_json()


        action_id = str(
            data.get(
                "action_id"
            )
        )


        action = pending_actions.pop(
            action_id,
            None
        )


        return jsonify({

            "success":
                True,

            "message":
                "Remediation rejected. "
                "No changes were made.",

            "action":
                action

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# START FLASK
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
