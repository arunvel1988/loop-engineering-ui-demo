import psutil
import subprocess


def check_server():

    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }


def check_processes():

    processes = []

    for process in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_percent"]
    ):

        try:

            processes.append(process.info)

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

    processes.sort(
        key=lambda x: x.get("cpu_percent", 0),
        reverse=True
    )

    return processes[:10]


def check_ports():

    connections = []

    for connection in psutil.net_connections(
        kind="inet"
    ):

        if connection.status == "LISTEN":

            connections.append({

                "pid": connection.pid,

                "local_address":
                    str(connection.laddr),

                "status":
                    connection.status
            })

    return connections


def check_docker():

    result = subprocess.run(

        [
            "docker",
            "ps",
            "--format",
            "{{.Names}} | {{.Status}} | {{.Image}}"
        ],

        capture_output=True,

        text=True
    )

    return result.stdout
