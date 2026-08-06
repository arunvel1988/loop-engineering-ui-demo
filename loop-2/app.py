from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify

from agent import run_agent

app = Flask(__name__)


@app.route("/")
def index():

    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():

    try:

        data = request.get_json()

        task = data.get("task", "")

        if task.strip() == "":

            return jsonify({
                "success": False,
                "message": "Task cannot be empty."
            }), 400

        result = run_agent(task)

        return jsonify({

            "success": True,

            "loops": result["loops"],

            "summary": result["summary"]

        })

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
