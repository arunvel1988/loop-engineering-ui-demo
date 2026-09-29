import os
import socket
import psutil
import subprocess
import sqlite3


# =========================================================
# DATABASE PATH
# =========================================================

DB_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "devops_agent.db"
)


# =========================================================
# CHECK SERVER
# =========================================================

def check_server():

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": memory.percent,
        "memory_available_gb": round(
            memory.available / (1024 ** 3),
            2
        ),
        "disk_percent": disk.percent,
        "disk_free_gb": round(
            disk.free / (1024 ** 3),
            2
        )
    }


# =========================================================
# CHECK PROCESSES
# =========================================================

def check_processes():

    processes = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "cpu_percent",
            "memory_percent"
        ]
    ):

        try:

            info = process.info

            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "username": info["username"],
                "cpu_percent": info["cpu_percent"],
                "memory_percent": round(
                    info["memory_percent"],
                    2
                )
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):

            continue


    # Sort highest CPU first

    processes.sort(
        key=lambda x: x["cpu_percent"],
        reverse=True
    )


    return {
        "processes": processes[:15]
    }


# =========================================================
# CHECK PORTS
# =========================================================

def check_ports():

    ports = []

    for connection in psutil.net_connections(
        kind="inet"
    ):

        try:

            if connection.status == psutil.CONN_LISTEN:

                ports.append({

                    "ip":
                        connection.laddr.ip,

                    "port":
                        connection.laddr.port,

                    "pid":
                        connection.pid

                })

        except Exception:

            continue


    return {
        "listening_ports": ports
    }


# =========================================================
# CHECK DOCKER
# =========================================================

def check_docker():

    try:

        result = subprocess.run(

            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{json .}}"
            ],

            capture_output=True,

            text=True,

            timeout=10

        )


        # Docker command failed

        if result.returncode != 0:

            return {

                "success": False,

                "error":
                    result.stderr.strip()

            }


        containers = []

        for line in result.stdout.splitlines():

            if line.strip():

                containers.append(line)


        return {

            "success": True,

            "containers": containers

        }


    except FileNotFoundError:

        return {

            "success": False,

            "error":
                "Docker command not found."

        }


    except subprocess.TimeoutExpired:

        return {

            "success": False,

            "error":
                "Docker command timed out."

        }


    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }


# =========================================================
# SEARCH PREVIOUS INCIDENTS
# =========================================================

def search_previous_incidents(
    alertname=None,
    severity=None,
    limit=5
):

    """
    Search historical incidents.

    IMPORTANT:
    This function intentionally returns a COMPACT result
    so that historical incidents do not consume too many
    tokens in the GPT context.
    """

    try:

        # -------------------------------------------------
        # Validate limit
        # -------------------------------------------------

        limit = int(limit)

        if limit < 1:
            limit = 1

        if limit > 5:
            limit = 5


        # -------------------------------------------------
        # Connect to SQLite
        # -------------------------------------------------

        conn = sqlite3.connect(
            DB_PATH
        )

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()


        # -------------------------------------------------
        # Query only useful fields
        # -------------------------------------------------

        query = """
            SELECT
                id,
                alertname,
                severity,
                instance,
                summary,
                agent_response,
                remediation_status
            FROM incidents
            WHERE 1 = 1
        """

        params = []


        # -------------------------------------------------
        # Alert filter
        # -------------------------------------------------

        if alertname:

            query += """
                AND alertname = ?
            """

            params.append(
                alertname
            )


        # -------------------------------------------------
        # Severity filter
        # -------------------------------------------------

        if severity:

            query += """
                AND severity = ?
            """

            params.append(
                severity
            )


        # -------------------------------------------------
        # Newest first
        # -------------------------------------------------

        query += """
            ORDER BY rowid DESC
            LIMIT ?
        """

        params.append(
            limit
        )


        cursor.execute(
            query,
            params
        )


        rows = cursor.fetchall()

        conn.close()


        # -------------------------------------------------
        # Compact result
        # -------------------------------------------------

        incidents = []


        for row in rows:

            response = (
                row["agent_response"]
                or ""
            )


            # ---------------------------------------------
            # IMPORTANT:
            #
            # Never send the complete previous agent
            # response to GPT.
            #
            # Keep only a small portion.
            # ---------------------------------------------

            response = response.strip()

            if len(response) > 1000:

                response = (
                    response[:1000]
                    + "..."
                )


            incidents.append({

                "id":
                    row["id"],

                "alertname":
                    row["alertname"],

                "severity":
                    row["severity"],

                "instance":
                    row["instance"],

                "summary":
                    row["summary"],

                "previous_investigation":
                    response,

                "remediation_status":
                    row["remediation_status"]

            })


        # -------------------------------------------------
        # Return compact historical evidence
        # -------------------------------------------------

        return {

            "success":
                True,

            "count":
                len(incidents),

            "incidents":
                incidents

        }


    except Exception as e:

        return {

            "success":
                False,

            "error":
                str(e)

        }


# =========================================================
# TERMINATE PROCESS
# =========================================================

def terminate_process(pid):

    try:

        # Make sure PID is an integer

        pid = int(pid)


        # -------------------------------------------------
        # Safety: Never terminate PID 1
        # -------------------------------------------------

        if pid == 1:

            return {

                "success": False,

                "error":
                    "Refusing to terminate PID 1."

            }


        # -------------------------------------------------
        # Get process
        # -------------------------------------------------

        process = psutil.Process(pid)


        # -------------------------------------------------
        # Get process information BEFORE termination
        # -------------------------------------------------

        process_name = process.name()

        target_user = process.username()


        # -------------------------------------------------
        # Identify current agent user
        # -------------------------------------------------

        current_user = (
            psutil.Process(
                os.getpid()
            ).username()
        )


        # -------------------------------------------------
        # Security check
        #
        # Only allow the agent to terminate processes
        # owned by the same user.
        # -------------------------------------------------

        if target_user != current_user:

            return {

                "success": False,

                "error":
                    f"Permission denied. "
                    f"Process belongs to "
                    f"{target_user}, "
                    f"but agent runs as "
                    f"{current_user}."

            }


        # -------------------------------------------------
        # Terminate process
        # -------------------------------------------------

        process.terminate()


        # -------------------------------------------------
        # Wait for graceful termination
        # -------------------------------------------------

        try:

            process.wait(
                timeout=5
            )


        # -------------------------------------------------
        # Force kill if necessary
        # -------------------------------------------------

        except psutil.TimeoutExpired:

            process.kill()

            process.wait(
                timeout=5
            )


        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        return {

            "success": True,

            "pid": pid,

            "process": process_name,

            "message":
                f"Process {process_name} "
                f"(PID {pid}) terminated successfully."

        }


    # -----------------------------------------------------
    # Process doesn't exist
    # -----------------------------------------------------

    except psutil.NoSuchProcess:

        return {

            "success": False,

            "error":
                f"Process PID {pid} does not exist."

        }


    # -----------------------------------------------------
    # Permission problem
    # -----------------------------------------------------

    except psutil.AccessDenied:

        return {

            "success": False,

            "error":
                f"Access denied while accessing "
                f"PID {pid}."

        }


    # -----------------------------------------------------
    # Invalid PID
    # -----------------------------------------------------

    except ValueError:

        return {

            "success": False,

            "error":
                f"Invalid PID: {pid}"

        }


    # -----------------------------------------------------
    # Other error
    # -----------------------------------------------------

    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }


# =========================================================
# TOOL REGISTRY
# =========================================================

TOOL_FUNCTIONS = {

    "check_server":
        check_server,

    "check_processes":
        check_processes,

    "check_ports":
        check_ports,

    "check_docker":
        check_docker,

    "search_previous_incidents":
        search_previous_incidents,

    "terminate_process":
        terminate_process

}
