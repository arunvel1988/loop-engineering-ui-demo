from flask import Flask, render_template, request, jsonify

from agent import run_agent
from tools import terminate_process


app = Flask(__name__)


# ---------------------------------------------------------
# Store pending remediation
# ---------------------------------------------------------

pending_actions = {}


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.route("/")
def index():

    return render_template("index.html")


# ---------------------------------------------------------
# CHAT
# ---------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        message = data.get("message", "").strip()

        if not message:

            return jsonify({
                "error": "Message cannot be empty"
            }), 400


        result = run_agent(message)


        pending_action = result.get("pending_action")


        # ---------------------------------------------
        # Store pending action
        # ---------------------------------------------

        if pending_action:

            action_id = str(
                pending_action["arguments"]["pid"]
            )

            pending_actions[action_id] = pending_action

            result["action_id"] = action_id


        return jsonify(result)


    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# APPROVE
# ---------------------------------------------------------

@app.route("/approve", methods=["POST"])
def approve():

    try:

        data = request.get_json()

        action_id = str(
            data.get("action_id")
        )


        action = pending_actions.get(action_id)


        if not action:

            return jsonify({

                "success": False,

                "error":
                    "Approval request not found or already processed."

            }), 404


        # ---------------------------------------------
        # Verify action
        # ---------------------------------------------

        if action["tool"] != "terminate_process":

            return jsonify({

                "success": False,

                "error": "Unknown remediation action."

            }), 400


        pid = action["arguments"]["pid"]


        # ---------------------------------------------
        # Execute remediation
        # ---------------------------------------------

        result = terminate_process(pid)


        # ---------------------------------------------
        # Remove pending action
        # ---------------------------------------------

        del pending_actions[action_id]


        return jsonify({

            "success": result.get("success", False),

            "action": action,

            "result": result

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ---------------------------------------------------------
# REJECT
# ---------------------------------------------------------

@app.route("/reject", methods=["POST"])
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

            "success": True,

            "message":
                "Remediation rejected by user.",

            "action": action

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
