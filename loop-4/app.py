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

import sqlite3
import threading
import json
import os

from datetime import datetime, timezone


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_PATH = os.path.join(
    BASE_DIR,
    "devops_agent.db"
)


def get_db():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_db()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # INCIDENTS TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (

            id TEXT PRIMARY KEY,

            alertname TEXT,

            status TEXT,

            severity TEXT,

            instance TEXT,

            summary TEXT,

            description TEXT,

            started_at TEXT,

            ended_at TEXT,

            agent_status TEXT,

            agent_message TEXT,

            agent_response TEXT,

            agent_error TEXT,

            action_id TEXT,

            pending_action TEXT,

            remediation_status TEXT,

            remediation_result TEXT,

            verification TEXT,

            raw_alert TEXT,

            created_at TEXT,

            updated_at TEXT

        )
    """)

    conn.commit()

    conn.close()


# ============================================================
# SHORT-TERM MEMORY DATABASE
# ============================================================

def init_memory_tables():

    conn = get_db()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # CONVERSATIONS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (

            conversation_id TEXT PRIMARY KEY,

            created_at TEXT,

            updated_at TEXT

        )
    """)

    # --------------------------------------------------------
    # CONVERSATION MESSAGES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            conversation_id TEXT,

            role TEXT,

            content TEXT,

            created_at TEXT

        )
    """)

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_messages_conversation
        ON messages(conversation_id, id)
    """)

    conn.commit()

    conn.close()


# Initialize both databases

init_db()

init_memory_tables()


# ============================================================
# IN-MEMORY APPROVAL ACTIONS
# ============================================================

# IMPORTANT:
#
# INCIDENTS are stored permanently in SQLite.
#
# pending_actions are temporary because they represent
# remediation actions waiting for human approval.
#
# Later these can also be persisted.

pending_actions = {}

action_lock = threading.Lock()


# ============================================================
# INCIDENT ID
# ============================================================

incident_lock = threading.Lock()


def generate_incident_id():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM incidents
        ORDER BY rowid DESC
        LIMIT 1
    """)

    row = cursor.fetchone()

    conn.close()

    if not row:

        number = 1

    else:

        try:

            last_id = row["id"]

            number = int(
                last_id.split("-")[1]
            ) + 1

        except Exception:

            number = 1

    return f"INC-{number:04d}"


# ============================================================
# TIME
# ============================================================

def now():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# SHORT-TERM MEMORY
# ============================================================

def create_conversation(
    conversation_id
):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO conversations (

            conversation_id,

            created_at,

            updated_at

        )
        VALUES (?, ?, ?)
    """, (

        conversation_id,

        now(),

        now()

    ))

    conn.commit()

    conn.close()


def update_conversation(
    conversation_id
):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE conversations

        SET updated_at = ?

        WHERE conversation_id = ?
    """, (

        now(),

        conversation_id

    ))

    conn.commit()

    conn.close()


def save_message(
    conversation_id,
    role,
    content
):

    if not content:

        return

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages (

            conversation_id,

            role,

            content,

            created_at

        )
        VALUES (?, ?, ?, ?)
    """, (

        conversation_id,

        role,

        content,

        now()

    ))

    conn.commit()

    conn.close()

    update_conversation(
        conversation_id
    )


def load_recent_messages(
    conversation_id,
    limit=8
):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            role,

            content,

            created_at

        FROM messages

        WHERE conversation_id = ?

        ORDER BY id DESC

        LIMIT ?
    """, (

        conversation_id,

        limit

    ))

    rows = cursor.fetchall()

    conn.close()

    # Database returns newest first.
    #
    # GPT needs the conversation in chronological order.

    rows = list(
        reversed(rows)
    )

    messages = []

    for row in rows:

        messages.append({

            "role":
                row["role"],

            "content":
                row["content"],

            "created_at":
                row["created_at"]

        })

    return messages


# ============================================================
# SAVE INCIDENT
# ============================================================

def save_incident(incident):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO incidents (

            id,

            alertname,

            status,

            severity,

            instance,

            summary,

            description,

            started_at,

            ended_at,

            agent_status,

            agent_message,

            agent_response,

            agent_error,

            action_id,

            pending_action,

            remediation_status,

            remediation_result,

            verification,

            raw_alert,

            created_at,

            updated_at

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (

        incident.get(
            "id"
        ),

        incident.get(
            "alertname",
            ""
        ),

        incident.get(
            "status",
            ""
        ),

        incident.get(
            "severity",
            ""
        ),

        incident.get(
            "instance",
            ""
        ),

        incident.get(
            "summary",
            ""
        ),

        incident.get(
            "description",
            ""
        ),

        incident.get(
            "started_at"
        ),

        incident.get(
            "ended_at"
        ),

        incident.get(
            "agent_status",
            ""
        ),

        incident.get(
            "agent_message",
            ""
        ),

        incident.get(
            "agent_response",
            ""
        ),

        incident.get(
            "agent_error",
            ""
        ),

        incident.get(
            "action_id"
        ),

        json.dumps(
            incident.get(
                "pending_action"
            )
        )
        if incident.get(
            "pending_action"
        )
        else None,

        incident.get(
            "remediation_status"
        ),

        json.dumps(
            incident.get(
                "remediation_result"
            )
        )
        if incident.get(
            "remediation_result"
        )
        else None,

        json.dumps(
            incident.get(
                "verification"
            )
        )
        if incident.get(
            "verification"
        )
        else None,

        json.dumps(
            incident.get(
                "raw_alert"
            )
        )
        if incident.get(
            "raw_alert"
        )
        else None,

        incident.get(
            "created_at",
            now()
        ),

        now()

    ))

    conn.commit()

    conn.close()


# ============================================================
# LOAD INCIDENT
# ============================================================

def load_incident(
    incident_id
):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM incidents
        WHERE id = ?
    """, (
        incident_id,
    ))

    row = cursor.fetchone()

    conn.close()

    if not row:

        return None

    incident = dict(row)

    # Convert JSON fields back to Python objects

    for field in [

        "pending_action",

        "remediation_result",

        "verification",

        "raw_alert"

    ]:

        if incident.get(field):

            try:

                incident[field] = json.loads(
                    incident[field]
                )

            except Exception:

                pass

    return incident


# ============================================================
# LOAD ALL INCIDENTS
# ============================================================

def load_all_incidents():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM incidents
        ORDER BY rowid DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    incidents = []

    for row in rows:

        incident = dict(row)

        for field in [

            "pending_action",

            "remediation_result",

            "verification",

            "raw_alert"

        ]:

            if incident.get(field):

                try:

                    incident[field] = json.loads(
                        incident[field]
                    )

                except Exception:

                    pass

        incidents.append(
            incident
        )

    return incidents


# ============================================================
# INDEX
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "error":
                    "Invalid JSON request."
            }), 400


        # ----------------------------------------------------
        # USER MESSAGE
        # ----------------------------------------------------

        message = data.get(
            "message",
            ""
        ).strip()


        if not message:

            return jsonify({
                "error":
                    "Message cannot be empty."
            }), 400


        # ----------------------------------------------------
        # CONVERSATION ID
        # ----------------------------------------------------

        conversation_id = data.get(
            "conversation_id"
        )


        # If browser does not have a conversation yet,
        # create one.

        if not conversation_id:

            conversation_id = os.urandom(
                8
            ).hex()


        # ----------------------------------------------------
        # CREATE CONVERSATION
        # ----------------------------------------------------

        create_conversation(
            conversation_id
        )


        # ----------------------------------------------------
        # LOAD SHORT-TERM MEMORY
        # ----------------------------------------------------

        history = load_recent_messages(
            conversation_id,
            limit=8
        )


        print()
        print(
            "=================================================="
        )

        print(
            "CHAT REQUEST"
        )

        print(
            "Conversation:",
            conversation_id
        )

        print(
            "Previous messages:",
            len(history)
        )

        print(
            "User:",
            message
        )

        print(
            "=================================================="
        )


        # ----------------------------------------------------
        # SAVE USER MESSAGE
        # ----------------------------------------------------

        save_message(
            conversation_id,
            "user",
            message
        )


        # ----------------------------------------------------
        # RUN AGENT
        # ----------------------------------------------------

        result = run_agent(
            message,
            conversation_history=history
        )


        # ----------------------------------------------------
        # SAVE ASSISTANT RESPONSE
        # ----------------------------------------------------

        assistant_response = result.get(
            "response",
            ""
        )


        if assistant_response:

            save_message(
                conversation_id,
                "assistant",
                assistant_response
            )


        # ----------------------------------------------------
        # APPROVAL
        # ----------------------------------------------------

        pending_action = result.get(
            "pending_action"
        )


        if pending_action:

            pid = pending_action[
                "arguments"
            ].get(
                "pid"
            )


            action_id = str(
                pid
            )


            with action_lock:

                pending_actions[
                    action_id
                ] = pending_action


            result[
                "action_id"
            ] = action_id


        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        result[
            "conversation_id"
        ] = conversation_id


        return jsonify(
            result
        )


    except Exception as e:

        print(
            "CHAT ERROR:",
            str(e)
        )

        return jsonify({
            "error":
                str(e)
        }), 500


# ============================================================
# AUTOMATIC INCIDENT INVESTIGATION
# ============================================================

def investigate_incident(
    incident_id
):

    print()

    print(
        "=================================================="
    )

    print(
        "STARTING AUTOMATIC INCIDENT INVESTIGATION"
    )

    print(
        "Incident:",
        incident_id
    )

    print(
        "=================================================="
    )


    incident = load_incident(
        incident_id
    )


    if not incident:

        print(
            "Incident no longer exists."
        )

        return


    # --------------------------------------------------------
    # STATUS: INVESTIGATING
    # --------------------------------------------------------

    incident[
        "agent_status"
    ] = "investigating"


    incident[
        "agent_message"
    ] = (
        "DevOps Agent is investigating this incident."
    )


    save_incident(
        incident
    )


    # --------------------------------------------------------
    # TASK FOR GPT
    # --------------------------------------------------------

    task = f"""
A production infrastructure incident has been
automatically detected.

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

The incident was generated automatically by
Alertmanager.

Investigate this incident using the available
infrastructure observation tools.

Do not assume the root cause.

Collect real telemetry and correlate the evidence.

Identify the root cause only when the evidence
supports it.

If a remediation is justified, propose it using
the available remediation mechanism.

Do not invent infrastructure information.

After investigation, provide:

Investigation Summary

Root Cause

Evidence

Recommended Remediation

Risk Assessment

Action Required
"""


    try:

        print(
            "Sending incident to GPT-OSS..."
        )


        result = run_agent(
            task
        )


        # ----------------------------------------------------
        # AGENT RESPONSE
        # ----------------------------------------------------

        incident[
            "agent_response"
        ] = result.get(
            "response",
            ""
        )


        pending_action = result.get(
            "pending_action"
        )


        # ----------------------------------------------------
        # REMEDIATION PROPOSED
        # ----------------------------------------------------

        if pending_action:

            pid = pending_action[
                "arguments"
            ].get(
                "pid"
            )


            action_id = (
                f"{incident_id}-{pid}"
            )


            action = {

                "tool":
                    pending_action[
                        "tool"
                    ],

                "arguments":
                    pending_action[
                        "arguments"
                    ],

                "incident_id":
                    incident_id

            }


            # ------------------------------------------------
            # STORE ACTION IN MEMORY
            # ------------------------------------------------

            with action_lock:

                pending_actions[
                    action_id
                ] = action


            # ------------------------------------------------
            # UPDATE INCIDENT
            # ------------------------------------------------

            incident[
                "action_id"
            ] = action_id


            incident[
                "pending_action"
            ] = pending_action


            incident[
                "remediation_status"
            ] = "waiting_for_approval"


            incident[
                "agent_status"
            ] = "waiting_for_approval"


            incident[
                "agent_message"
            ] = (
                "The DevOps Agent identified a "
                "remediation action. Human approval "
                "is required."
            )


        else:

            incident[
                "agent_status"
            ] = "completed"


            incident[
                "agent_message"
            ] = (
                "Investigation completed."
            )


        save_incident(
            incident
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
            incident[
                "agent_status"
            ]
        )

        print(
            "=================================================="
        )


    except Exception as e:

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


        incident[
            "agent_status"
        ] = "failed"


        incident[
            "agent_message"
        ] = (
            "Automatic investigation failed."
        )


        incident[
            "agent_error"
        ] = str(e)


        save_incident(
            incident
        )


# ============================================================
# ALERTMANAGER WEBHOOK
# ============================================================

@app.route(
    "/webhook/alert",
    methods=["POST"]
)
def alert_webhook():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success": False,

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


        alerts = data.get(
            "alerts",
            []
        )


        created_incidents = []


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


            # ------------------------------------------------
            # INCIDENT ID
            # ------------------------------------------------

            with incident_lock:

                incident_id = (
                    generate_incident_id()
                )


            # ------------------------------------------------
            # CREATE INCIDENT
            # ------------------------------------------------

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
                    "Incident received. Investigation is starting.",

                "agent_response":
                    "",

                "agent_error":
                    "",

                "action_id":
                    None,

                "pending_action":
                    None,

                "remediation_status":
                    None,

                "remediation_result":
                    None,

                "verification":
                    None,

                "raw_alert":
                    alert,

                "created_at":
                    now(),

                "updated_at":
                    now()

            }


            # ------------------------------------------------
            # SAVE IMMEDIATELY
            # ------------------------------------------------

            save_incident(
                incident
            )


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


            # ------------------------------------------------
            # START AGENT
            # ------------------------------------------------

            investigation_thread = (
                threading.Thread(

                    target=
                        investigate_incident,

                    args=(
                        incident_id,
                    ),

                    daemon=True

                )
            )


            investigation_thread.start()


        print()

        print(
            "=================================================="
        )


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


# ============================================================
# GET ALL INCIDENTS
# ============================================================

@app.route(
    "/incidents",
    methods=["GET"]
)
def get_incidents():

    try:

        incidents = (
            load_all_incidents()
        )


        return jsonify({

            "success":
                True,

            "incidents":
                incidents

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# GET ONE INCIDENT
# ============================================================

@app.route(
    "/incidents/<incident_id>",
    methods=["GET"]
)
def get_incident(
    incident_id
):

    incident = load_incident(
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


# ============================================================
# APPROVE REMEDIATION
# ============================================================

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


        # ----------------------------------------------------
        # GET ACTION
        # ----------------------------------------------------

        with action_lock:

            action = pending_actions.get(
                action_id
            )


        if not action:

            return jsonify({

                "success":
                    False,

                "error":
                    "Approval request not found or already processed."

            }), 404


        # ----------------------------------------------------
        # VALIDATE TOOL
        # ----------------------------------------------------

        if action.get(
            "tool"
        ) != "terminate_process":

            return jsonify({

                "success":
                    False,

                "error":
                    "Unknown remediation action."

            }), 400


        # ----------------------------------------------------
        # GET INCIDENT
        # ----------------------------------------------------

        incident_id = action.get(
            "incident_id"
        )


        incident = None


        if incident_id:

            incident = load_incident(
                incident_id
            )


        # ----------------------------------------------------
        # MARK EXECUTING
        # ----------------------------------------------------

        if incident:

            incident[
                "remediation_status"
            ] = "executing"


            incident[
                "agent_message"
            ] = (
                "Human approval received. "
                "Executing remediation."
            )


            save_incident(
                incident
            )


        # ----------------------------------------------------
        # EXECUTE
        # ----------------------------------------------------

        pid = action[
            "arguments"
        ].get(
            "pid"
        )


        print()

        print(
            "=================================================="
        )

        print(
            "EXECUTING APPROVED REMEDIATION"
        )

        print(
            "Action:",
            action
        )

        print(
            "=================================================="
        )


        result = terminate_process(
            pid
        )


        # ----------------------------------------------------
        # REMOVE PENDING ACTION
        # ----------------------------------------------------

        with action_lock:

            pending_actions.pop(
                action_id,
                None
            )


        # ----------------------------------------------------
        # VERIFY
        # ----------------------------------------------------

        server_after = (
            check_server()
        )


        processes_after = (
            check_processes()
        )


        verification = {

            "server":
                server_after,

            "processes":
                processes_after

        }


        # ----------------------------------------------------
        # UPDATE INCIDENT
        # ----------------------------------------------------

        if incident:

            incident[
                "pending_action"
            ] = None


            incident[
                "remediation_result"
            ] = result


            incident[
                "verification"
            ] = verification


            if result.get(
                "success"
            ):

                incident[
                    "remediation_status"
                ] = "executed"


                incident[
                    "agent_status"
                ] = "completed"


                incident[
                    "agent_message"
                ] = (
                    "Remediation executed successfully "
                    "and verification completed."
                )


            else:

                incident[
                    "remediation_status"
                ] = "failed"


                incident[
                    "agent_status"
                ] = "completed"


                incident[
                    "agent_message"
                ] = (
                    "Remediation execution failed."
                )


            save_incident(
                incident
            )


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

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

            "verification":
                verification

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# REJECT REMEDIATION
# ============================================================

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


        with action_lock:

            action = pending_actions.pop(
                action_id,
                None
            )


        if not action:

            return jsonify({

                "success":
                    False,

                "error":
                    "Approval request not found or already processed."

            }), 404


        incident_id = action.get(
            "incident_id"
        )


        incident = None


        if incident_id:

            incident = load_incident(
                incident_id
            )


        # ----------------------------------------------------
        # UPDATE INCIDENT
        # ----------------------------------------------------

        if incident:

            incident[
                "pending_action"
            ] = None


            incident[
                "remediation_status"
            ] = "rejected"


            incident[
                "agent_status"
            ] = "completed"


            incident[
                "agent_message"
            ] = (
                "Human approval was rejected. "
                "No infrastructure changes were made."
            )


            save_incident(
                incident
            )


        return jsonify({

            "success":
                True,

            "message":
                "Remediation rejected. No changes were made.",

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


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    print()

    print(
        "=================================================="
    )

    print(
        "DEVOPS AGENT STARTING"
    )

    print(
        "Database:",
        DB_PATH
    )

    print(
        "Short-term memory: ENABLED"
    )

    print(
        "=================================================="
    )


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True,

        use_reloader=False

    )
