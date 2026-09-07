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


app = Flask(__name__)


# =========================================================
# PENDING ACTIONS
# =========================================================

pending_actions = {}


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

        result = run_agent(message)


        # -------------------------------------------------
        # Check pending remediation
        # -------------------------------------------------

        pending_action = (
            result.get("pending_action")
        )


        if pending_action:

            pid = pending_action[
                "arguments"
            ]["pid"]


            action_id = str(pid)


            pending_actions[action_id] = (
                pending_action
            )


            result["action_id"] = (
                action_id
            )


        return jsonify(result)


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


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
            data.get("action_id")
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

        if action["tool"] != "terminate_process":

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
            data.get("action_id")
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
