"""
k8s_tools.py

A toolkit for inspecting a Kubernetes cluster's health - built on the
official `kubernetes` Python client. Read-only by design: listing pods,
events, logs, resource usage, and describing problems. No functions here
delete or modify cluster state.

--------------------------------------------------------------------
ONE-TIME SETUP
--------------------------------------------------------------------
1. pip install kubernetes

2. Make sure you have a working kubeconfig (the same file `kubectl` uses,
   usually ~/.kube/config), and that `kubectl get nodes` works from this
   machine.

3. (Optional) For resource metrics (`top pod`/`top node` equivalents),
   the metrics-server must be installed in the cluster:
     kubectl top nodes
   If that command fails, get_resource_usage() below will too.
--------------------------------------------------------------------
"""

from kubernetes import client, config

_v1 = None
_apps_v1 = None


# ============================================================
# AUTH / CLIENT SETUP
# ============================================================

def _get_clients():
    global _v1, _apps_v1
    if _v1 is not None:
        return _v1, _apps_v1

    config.load_kube_config()  # reads ~/.kube/config, same as kubectl
    _v1 = client.CoreV1Api()
    _apps_v1 = client.AppsV1Api()
    return _v1, _apps_v1


# ============================================================
# CLUSTER OVERVIEW
# ============================================================

def list_namespaces():
    """List all namespaces in the cluster."""
    v1, _ = _get_clients()
    ns = v1.list_namespace()
    return [n.metadata.name for n in ns.items]


def list_nodes():
    """List nodes with their status (Ready/NotReady) and key conditions."""
    v1, _ = _get_clients()
    nodes = v1.list_node()
    result = []
    for n in nodes.items:
        conditions = {c.type: c.status for c in n.status.conditions}
        result.append({
            "name": n.metadata.name,
            "ready": conditions.get("Ready") == "True",
            "conditions": conditions,
            "kubelet_version": n.status.node_info.kubelet_version,
        })
    return result


# ============================================================
# PODS
# ============================================================

def list_pods(namespace=None, only_problems=False):
    """
    List pods, optionally filtered to a namespace, optionally filtered
    to only pods that look unhealthy (not Running/Succeeded, high restarts,
    or not all containers ready).
    """
    v1, _ = _get_clients()
    pods = v1.list_namespaced_pod(namespace) if namespace else v1.list_pod_for_all_namespaces()

    result = []
    for p in pods.items:
        restarts = sum(cs.restart_count for cs in (p.status.container_statuses or []))
        ready_count = sum(1 for cs in (p.status.container_statuses or []) if cs.ready)
        total_containers = len(p.status.container_statuses or [])
        phase = p.status.phase

        is_problem = (
            phase not in ("Running", "Succeeded")
            or restarts > 0
            or ready_count < total_containers
        )

        info = {
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "phase": phase,
            "restarts": restarts,
            "ready": f"{ready_count}/{total_containers}",
            "node": p.spec.node_name,
            "start_time": str(p.status.start_time) if p.status.start_time else None,
            "is_problem": is_problem,
        }

        if not only_problems or is_problem:
            result.append(info)

    return result


def describe_pod(name, namespace):
    """Get detailed status for one pod, including container states and reasons for failure."""
    v1, _ = _get_clients()
    p = v1.read_namespaced_pod(name=name, namespace=namespace)

    containers = []
    for cs in (p.status.container_statuses or []):
        state = cs.state
        state_desc = "unknown"
        reason = None
        if state.running:
            state_desc = "running"
        elif state.waiting:
            state_desc = "waiting"
            reason = state.waiting.reason  # e.g. CrashLoopBackOff, ImagePullBackOff
        elif state.terminated:
            state_desc = "terminated"
            reason = state.terminated.reason  # e.g. OOMKilled, Error

        containers.append({
            "name": cs.name,
            "state": state_desc,
            "reason": reason,
            "restart_count": cs.restart_count,
            "image": cs.image,
        })

    return {
        "name": p.metadata.name,
        "namespace": p.metadata.namespace,
        "phase": p.status.phase,
        "node": p.spec.node_name,
        "containers": containers,
        "conditions": [
            {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
            for c in (p.status.conditions or [])
        ],
    }


def get_pod_logs(name, namespace, tail_lines=100, previous=False):
    """
    Get recent logs for a pod's (first) container.
    Set previous=True to get logs from the last crashed instance
    (essential for debugging CrashLoopBackOff).
    """
    v1, _ = _get_clients()
    try:
        return v1.read_namespaced_pod_log(
            name=name, namespace=namespace, tail_lines=tail_lines, previous=previous
        )
    except client.exceptions.ApiException as e:
        return f"Error fetching logs: {e.reason}"


# ============================================================
# EVENTS (often the fastest way to spot *why* something is broken)
# ============================================================

def get_events(namespace=None, only_warnings=True, max_results=50):
    """
    List recent cluster events. Warnings (Failed scheduling, BackOff,
    Unhealthy, FailedMount, etc.) are usually what you want when
    hunting for issues.
    """
    v1, _ = _get_clients()
    events = v1.list_namespaced_event(namespace) if namespace else v1.list_event_for_all_namespaces()

    result = []
    for e in events.items:
        if only_warnings and e.type != "Warning":
            continue
        result.append({
            "namespace": e.metadata.namespace,
            "object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "reason": e.reason,
            "message": e.message,
            "type": e.type,
            "count": e.count,
            "last_seen": str(e.last_timestamp) if e.last_timestamp else None,
        })

    result.sort(key=lambda x: x["last_seen"] or "", reverse=True)
    return result[:max_results]


# ============================================================
# DEPLOYMENTS
# ============================================================

def list_deployments(namespace=None, only_problems=False):
    """List deployments and flag ones where ready replicas < desired replicas."""
    _, apps_v1 = _get_clients()
    deployments = (
        apps_v1.list_namespaced_deployment(namespace)
        if namespace else apps_v1.list_deployment_for_all_namespaces()
    )

    result = []
    for d in deployments.items:
        desired = d.spec.replicas or 0
        ready = d.status.ready_replicas or 0
        is_problem = ready < desired

        info = {
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "desired_replicas": desired,
            "ready_replicas": ready,
            "is_problem": is_problem,
        }

        if not only_problems or is_problem:
            result.append(info)

    return result


# ============================================================
# RESOURCE USAGE (requires metrics-server)
# ============================================================

def get_resource_usage(namespace=None):
    """
    Get CPU/memory usage per pod via the metrics API.
    Requires metrics-server to be installed in the cluster.
    """
    from kubernetes.client import CustomObjectsApi
    v1, _ = _get_clients()
    custom_api = CustomObjectsApi()

    try:
        if namespace:
            metrics = custom_api.list_namespaced_custom_object(
                "metrics.k8s.io", "v1beta1", namespace, "pods"
            )
        else:
            metrics = custom_api.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "pods"
            )
    except client.exceptions.ApiException as e:
        return f"Error: metrics-server may not be installed ({e.reason})"

    result = []
    for item in metrics.get("items", []):
        containers = item.get("containers", [])
        result.append({
            "name": item["metadata"]["name"],
            "namespace": item["metadata"]["namespace"],
            "containers": [
                {"name": c["name"], "cpu": c["usage"]["cpu"], "memory": c["usage"]["memory"]}
                for c in containers
            ],
        })
    return result
