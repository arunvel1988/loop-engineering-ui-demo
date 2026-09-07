import os
import psutil
import subprocess


# ============================================================
# 1. SERVER HEALTH
# ============================================================

def check_server():
    """
    Check overall server health.
    """

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "hostname": os.uname().nodename,

        "cpu_percent":
            psutil.cpu_percent(interval=1),

        "memory_percent":
            memory.percent,

        "memory_available_gb":
            round(memory.available / (1024 ** 3), 2),

        "disk_percent":
            disk.percent,

        "disk_free_gb":
            round(disk.free / (1024 ** 3), 2)
    }


# ============================================================
# 2. PROCESS INVESTIGATION
# ============================================================

def check_processes():
    """
    Find processes consuming high CPU or memory.
    """

    processes = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "cpu_percent",
            "memory_percent",
            "status"
        ]
    ):

        try:

            info = process.info

            processes.append({

                "pid":
                    info["pid"],

                "name":
                    info["name"],

                "username":
                    info["username"],

                "cpu_percent":
                    info["cpu_percent"],

                "memory_percent":
                    info["memory_percent"],

                "status":
                    info["status"]
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):

            continue


    # Sort by CPU

    processes.sort(
        key=lambda x: x["cpu_percent"] or 0,
        reverse=True
    )


    return processes[:15]


# ============================================================
# 3. NETWORK PORT INVESTIGATION
# ============================================================

def check_ports():
    """
    Check listening TCP/UDP ports.
    """

    ports = []

    try:

        connections = psutil.net_connections(
            kind="inet"
        )

        for connection in connections:

            if connection.status == "LISTEN":

                ports.append({

                    "pid":
                        connection.pid,

                    "local_address":
                        str(connection.laddr),

                    "status":
                        connection.status
                })

    except psutil.AccessDenied:

        return {
            "error":
                "Permission denied while reading network connections"
        }


    return ports


# ============================================================
# 4. DOCKER INVESTIGATION
# ============================================================

def check_docker():
    """
    Check Docker containers.
    """

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

            timeout=15
        )


        if result.returncode != 0:

            return {

                "success": False,

                "error":
                    result.stderr
            }


        containers = []

        for line in result.stdout.splitlines():

            if line.strip():

                containers.append(line)


        return {

            "success": True,

            "containers":
                containers
        }


    except Exception as e:

        return {

            "success": False,

            "error":
                str(e)
        }


# ============================================================
# 5. TERMINATE PROCESS
# ============================================================

def terminate_process(pid):
    """
    Terminate a process.

    Safety:
    - PID 1 cannot be terminated.
    - Process must belong to the same user running the agent.
    """

    try:

        pid = int(pid)


        # Safety protection

        if pid == 1:

            return {

                "success": False,

                "error":
                    "Refusing to terminate PID 1"
            }


        process = psutil.Process(pid)


        # Check owner

        current_user = psutil.Process(
            os.getpid()
        ).username()

        process_user = process.username()


        if process_user != current_user:

            return {

                "success": False,

                "error":
                    "Process belongs to another user"
            }


        process_name = process.name()


        # Graceful termination

        process.terminate()


        try:

            process.wait(timeout=5)

        except psutil.TimeoutExpired:

            process.kill()

            process.wait(timeout=5)


        return {

            "success": True,

            "pid":
                pid,

            "process":
                process_name,

            "message":
                f"Process {pid} terminated successfully"
        }


    except psutil.NoSuchProcess:

        return {

            "success": False,

            "error":
                f"Process {pid} does not exist"
        }


    except psutil.AccessDenied:

        return {

            "success": False,

            "error":
                "Permission denied"
        }


    except Exception as e:

        return {

            "success": False,

            "error":
                str(e)
        }


# ============================================================
# TOOL REGISTRY
# ============================================================

TOOL_FUNCTIONS = {

    "check_server":
        check_server,

    "check_processes":
        check_processes,

    "check_ports":
        check_ports,

    "check_docker":
        check_docker,

    "terminate_process":
        terminate_process
}
