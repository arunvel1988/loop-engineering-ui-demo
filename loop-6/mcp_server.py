import os
import re
import signal
import subprocess

import psutil
import docker

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------
# MCP SERVER
# ---------------------------------------------------------

mcp = FastMCP("DevOps MCP Server")


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def get_docker_client():
    return docker.from_env()


def validate_pid(pid: int):
    if pid <= 0:
        raise ValueError("PID must be greater than 0")

    if pid == 1:
        raise ValueError("PID 1 cannot be terminated")

    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        raise ValueError(f"Process {pid} does not exist")

    current_user = os.getuid()

    try:
        process_user = process.uids().real
    except Exception:
        process_user = None

    if process_user is not None and process_user != current_user:
        raise PermissionError(
            f"Process {pid} does not belong to the MCP server user"
        )

    return process


def validate_service_name(name: str):
    if not re.fullmatch(r"[a-zA-Z0-9_.@:-]+", name):
        raise ValueError("Invalid systemd service name")


# ---------------------------------------------------------
# LINUX TOOLS
# ---------------------------------------------------------

@mcp.tool()
def check_server() -> dict:
    """
    Return current server CPU, memory, disk and uptime information.
    """

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot_time = psutil.boot_time()

    return {
        "hostname": os.uname().nodename,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "memory_percent": memory.percent,
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "memory_available_gb": round(memory.available / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "uptime_seconds": int(__import__("time").time() - boot_time),
    }


@mcp.tool()
def check_processes(limit: int = 15) -> list:
    """
    Return processes sorted by CPU usage.
    """

    limit = max(1, min(limit, 50))

    processes = []

    for process in psutil.process_iter(
        ["pid", "name", "username", "status", "cpu_percent", "memory_percent"]
    ):
        try:
            info = process.info

            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "username": info["username"],
                "status": info["status"],
                "cpu_percent": info["cpu_percent"],
                "memory_percent": round(
                    info["memory_percent"] or 0, 2
                ),
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    processes.sort(
        key=lambda x: x["cpu_percent"] or 0,
        reverse=True,
    )

    return processes[:limit]


@mcp.tool()
def check_ports() -> list:
    """
    Return listening TCP/UDP ports.
    """

    results = []

    for connection in psutil.net_connections(kind="inet"):

        if connection.status != psutil.CONN_LISTEN:
            continue

        address = connection.laddr

        results.append({
            "protocol": "tcp" if connection.type == 1 else "udp",
            "ip": address.ip,
            "port": address.port,
            "pid": connection.pid,
        })

    results.sort(key=lambda x: x["port"])

    return results


@mcp.tool()
def inspect_process(pid: int) -> dict:
    """
    Inspect a specific process.
    """

    process = psutil.Process(pid)

    return {
        "pid": process.pid,
        "name": process.name(),
        "username": process.username(),
        "status": process.status(),
        "cpu_percent": process.cpu_percent(interval=0.5),
        "memory_percent": round(process.memory_percent(), 2),
        "cmdline": process.cmdline(),
        "create_time": process.create_time(),
    }


@mcp.tool()
def terminate_process(pid: int) -> dict:
    """
    Gracefully terminate a process owned by the MCP server user.
    """

    process = validate_pid(pid)

    process.terminate()

    try:
        process.wait(timeout=5)
        return {
            "success": True,
            "action": "terminate",
            "pid": pid,
            "message": f"Process {pid} terminated successfully",
        }

    except psutil.TimeoutExpired:
        return {
            "success": False,
            "action": "terminate",
            "pid": pid,
            "message": (
                f"Process {pid} did not terminate within 5 seconds"
            ),
        }


@mcp.tool()
def force_terminate_process(pid: int) -> dict:
    """
    Force kill a process owned by the MCP server user.
    """

    process = validate_pid(pid)

    process.kill()

    try:
        process.wait(timeout=5)

        return {
            "success": True,
            "action": "kill",
            "pid": pid,
            "message": f"Process {pid} killed successfully",
        }

    except psutil.TimeoutExpired:
        return {
            "success": False,
            "action": "kill",
            "pid": pid,
            "message": f"Process {pid} could not be killed",
        }


# ---------------------------------------------------------
# SYSTEMD TOOLS
# ---------------------------------------------------------

@mcp.tool()
def service_status(service: str) -> dict:
    """
    Get systemd service status.
    """

    validate_service_name(service)

    result = subprocess.run(
        ["systemctl", "is-active", service],
        capture_output=True,
        text=True,
    )

    active = result.stdout.strip()

    return {
        "service": service,
        "active": active == "active",
        "status": active,
    }


@mcp.tool()
def start_service(service: str) -> dict:
    """
    Start a systemd service.
    """

    validate_service_name(service)

    result = subprocess.run(
        ["systemctl", "start", service],
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "service": service,
        "action": "start",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@mcp.tool()
def stop_service(service: str) -> dict:
    """
    Stop a systemd service.
    """

    validate_service_name(service)

    result = subprocess.run(
        ["systemctl", "stop", service],
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "service": service,
        "action": "stop",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@mcp.tool()
def restart_service(service: str) -> dict:
    """
    Restart a systemd service.
    """

    validate_service_name(service)

    result = subprocess.run(
        ["systemctl", "restart", service],
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "service": service,
        "action": "restart",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------
# DOCKER TOOLS
# ---------------------------------------------------------

@mcp.tool()
def check_docker() -> list:
    """
    Return Docker containers.
    """

    client = get_docker_client()

    containers = client.containers.list(all=True)

    result = []

    for container in containers:

        result.append({
            "id": container.short_id,
            "name": container.name,
            "image": (
                container.image.tags[0]
                if container.image.tags
                else str(container.image.id)
            ),
            "status": container.status,
        })

    return result


@mcp.tool()
def inspect_container(container: str) -> dict:
    """
    Inspect a Docker container.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    return {
        "id": obj.short_id,
        "name": obj.name,
        "status": obj.status,
        "image": (
            obj.image.tags[0]
            if obj.image.tags
            else str(obj.image.id)
        ),
        "ports": obj.attrs["NetworkSettings"]["Ports"],
        "restart_policy": obj.attrs["HostConfig"]["RestartPolicy"],
    }


@mcp.tool()
def docker_logs(
    container: str,
    tail: int = 100,
) -> str:
    """
    Return recent Docker container logs.
    """

    client = get_docker_client()

    tail = max(1, min(tail, 500))

    obj = client.containers.get(container)

    logs = obj.logs(
        tail=tail,
        timestamps=True,
    )

    return logs.decode(
        "utf-8",
        errors="replace",
    )


@mcp.tool()
def docker_stats(container: str) -> dict:
    """
    Return current Docker container resource statistics.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    stats = obj.stats(stream=False)

    cpu_stats = stats["cpu_stats"]
    previous_cpu = stats["precpu_stats"]

    cpu_delta = (
        cpu_stats["cpu_usage"]["total_usage"]
        - previous_cpu["cpu_usage"]["total_usage"]
    )

    system_delta = (
        cpu_stats["system_cpu_usage"]
        - previous_cpu["system_cpu_usage"]
    )

    online_cpus = cpu_stats.get(
        "online_cpus",
        len(cpu_stats["cpu_usage"].get("percpu_usage", []))
        or 1,
    )

    if system_delta > 0:
        cpu_percent = (
            cpu_delta / system_delta
        ) * online_cpus * 100
    else:
        cpu_percent = 0

    memory = stats["memory_stats"]

    return {
        "container": obj.name,
        "status": obj.status,
        "cpu_percent": round(cpu_percent, 2),
        "memory_usage_mb": round(
            memory.get("usage", 0) / (1024 ** 2),
            2,
        ),
        "memory_limit_mb": round(
            memory.get("limit", 0) / (1024 ** 2),
            2,
        ),
    }


@mcp.tool()
def start_container(container: str) -> dict:
    """
    Start a stopped Docker container.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    obj.start()

    return {
        "success": True,
        "container": obj.name,
        "action": "start",
        "status": obj.status,
    }


@mcp.tool()
def stop_container(container: str) -> dict:
    """
    Stop a running Docker container.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    obj.stop(timeout=10)

    return {
        "success": True,
        "container": obj.name,
        "action": "stop",
    }


@mcp.tool()
def restart_container(container: str) -> dict:
    """
    Restart a Docker container.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    obj.restart(timeout=10)

    return {
        "success": True,
        "container": obj.name,
        "action": "restart",
    }


@mcp.tool()
def remove_container(
    container: str,
    force: bool = False,
) -> dict:
    """
    Remove a Docker container.

    Running containers require force=True.
    """

    client = get_docker_client()

    obj = client.containers.get(container)

    if obj.status == "running" and not force:
        return {
            "success": False,
            "container": obj.name,
            "message": (
                "Container is running. "
                "Set force=True to remove it."
            ),
        }

    obj.remove(force=force)

    return {
        "success": True,
        "container": container,
        "action": "remove",
    }


# ---------------------------------------------------------
# SERVER START
# ---------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("DevOps MCP Server")
    print("=" * 60)
    print("Transport : Streamable HTTP")
    print("Endpoint  : http://0.0.0.0:8080/mcp")
    print("=" * 60)

    mcp.run(
        transport="streamable-http"
    )
