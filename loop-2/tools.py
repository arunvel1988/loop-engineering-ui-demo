import os
import psutil
import subprocess


def check_server():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "hostname": psutil.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": memory.percent,
        "memory_available_gb": round(memory.available / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2)
    }


def check_processes():
    processes = []

    for process in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent"]
    ):
        try:
            info = process.info

            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "username": info["username"],
                "cpu_percent": info["cpu_percent"],
                "memory_percent": round(info["memory_percent"], 2)
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(
        key=lambda x: x["cpu_percent"],
        reverse=True
    )

    return {
        "processes": processes[:15]
    }


def check_ports():
    ports = []

    for conn in psutil.net_connections(kind="inet"):
        try:
            if conn.status == psutil.CONN_LISTEN:

                ports.append({
                    "ip": conn.laddr.ip,
                    "port": conn.laddr.port,
                    "pid": conn.pid
                })

        except Exception:
            continue

    return {
        "listening_ports": ports
    }


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

        if result.returncode != 0:
            return {
                "error": result.stderr.strip()
            }

        containers = []

        for line in result.stdout.splitlines():

            if line.strip():

                containers.append(line)

        return {
            "containers": containers
        }

    except Exception as e:

        return {
            "error": str(e)
        }


def terminate_process(pid):

    try:
        pid = int(pid)

        if pid == 1:
            return {
                "success": False,
                "error": "Refusing to terminate PID 1."
            }

        process = psutil.Process(pid)

        # Security check:
        # Only allow terminating processes owned by the
        # same user running the agent.

        current_user = psutil.Process(os.getpid()).username()
        target_user = process.username()

        if target_user != current_user:

            return {
                "success": False,
                "error": (
                    f"Permission denied. Process belongs to "
                    f"{target_user}, agent runs as {current_user}."
                )
            }

        process_name = process.name()

        process.terminate()

        try:
            process.wait(timeout=5)

        except psutil.TimeoutExpired:

            process.kill()
            process.wait(timeout=5)

        return {
            "success": True,
            "pid": pid,
            "process": process_name,
            "message": f"Process {process_name} (PID {pid}) terminated."
        }

    except psutil.NoSuchProcess:

        return {
            "success": False,
            "error": f"Process PID {pid} does not exist."
        }

    except psutil.AccessDenied:

        return {
            "success": False,
            "error": f"Access denied while terminating PID {pid}."
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ---------------------------------------------------------
# TOOL REGISTRY
# ---------------------------------------------------------

TOOL_FUNCTIONS = {

    "check_server": check_server,

    "check_processes": check_processes,

    "check_ports": check_ports,

    "check_docker": check_docker,

    "terminate_process": terminate_process

}
