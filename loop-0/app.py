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

    task = request.json["task"]

    result = run_agent(task)

    return jsonify(result)


if __name__ == "__main__":

    app.run(debug=True)
