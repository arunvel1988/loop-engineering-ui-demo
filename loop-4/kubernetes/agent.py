from k8s_tools import (
    list_pods,
    describe_pod,
    get_pod_logs,
    get_events,
    list_deployments,
    list_nodes,
)
from ollama_client import ask_planner
from ollama_client import summarize_cluster


def run_agent(goal):

    context = []

    loops = []

    pods = []

    events = []

    deployments = []

    nodes = []

    described = {}   # "namespace/name" -> describe_pod() result
    logs = {}         # "namespace/name" -> log text

    summary = ""

    findings = {}  # everything gathered so far, passed to summarizer

    while True:

        planner = ask_planner(goal, context)

        thought = planner["thought"]
        action = planner["action"]

        arguments = planner.get("arguments", {})

        observation = ""

        # --------------------------------------------------
        # READ PODS
        # --------------------------------------------------

        if action == "READ_PODS":

            namespace = arguments.get("namespace")
            only_problems = arguments.get("only_problems", False)

            pods = list_pods(namespace=namespace, only_problems=only_problems)

            observation = f"{len(pods)} pod(s) found."

            if pods:

                ids_preview = ", ".join(
                    f"{p.get('namespace')}/{p.get('name')}:{p.get('phase')}" for p in pods
                )

                observation += f" [{ids_preview}]"

            findings["pods"] = pods

        # --------------------------------------------------
        # READ EVENTS
        # --------------------------------------------------

        elif action == "READ_EVENTS":

            namespace = arguments.get("namespace")
            only_warnings = arguments.get("only_warnings", True)
            max_results = arguments.get("max_results", 50)

            events = get_events(
                namespace=namespace,
                only_warnings=only_warnings,
                max_results=max_results,
            )

            observation = f"{len(events)} warning event(s) found."

            if events:

                preview = ", ".join(
                    f"{e.get('object')}:{e.get('reason')}" for e in events[:10]
                )

                observation += f" [{preview}]"

            findings["events"] = events

        # --------------------------------------------------
        # READ DEPLOYMENTS
        # --------------------------------------------------

        elif action == "READ_DEPLOYMENTS":

            namespace = arguments.get("namespace")
            only_problems = arguments.get("only_problems", False)

            deployments = list_deployments(namespace=namespace, only_problems=only_problems)

            observation = f"{len(deployments)} deployment(s) found."

            if deployments:

                preview = ", ".join(
                    f"{d.get('namespace')}/{d.get('name')}:"
                    f"{d.get('ready_replicas')}/{d.get('desired_replicas')}"
                    for d in deployments
                )

                observation += f" [{preview}]"

            findings["deployments"] = deployments

        # --------------------------------------------------
        # READ NODES
        # --------------------------------------------------

        elif action == "READ_NODES":

            nodes = list_nodes()

            not_ready = [n for n in nodes if not n.get("ready")]

            observation = f"{len(nodes)} node(s) found, {len(not_ready)} not Ready."

            findings["nodes"] = nodes

        # --------------------------------------------------
        # DESCRIBE POD
        # --------------------------------------------------

        elif action == "DESCRIBE_POD":

            name = arguments.get("name")
            namespace = arguments.get("namespace")

            if not name or not namespace:

                observation = "DESCRIBE_POD requires 'name' and 'namespace' arguments."

            else:

                key = f"{namespace}/{name}"

                try:

                    detail = describe_pod(name=name, namespace=namespace)

                    described[key] = detail

                    reasons = [
                        c.get("reason") for c in detail.get("containers", []) if c.get("reason")
                    ]

                    observation = f"Described {key}. Container states/reasons: {reasons}"

                    findings.setdefault("described_pods", {})[key] = detail

                except Exception as e:

                    observation = f"Failed to describe pod {key}: {e}"

        # --------------------------------------------------
        # GET LOGS
        # --------------------------------------------------

        elif action == "GET_LOGS":

            name = arguments.get("name")
            namespace = arguments.get("namespace")
            tail_lines = arguments.get("tail_lines", 100)
            previous = arguments.get("previous", False)

            if not name or not namespace:

                observation = "GET_LOGS requires 'name' and 'namespace' arguments."

            else:

                key = f"{namespace}/{name}"

                log_text = get_pod_logs(
                    name=name,
                    namespace=namespace,
                    tail_lines=tail_lines,
                    previous=previous,
                )

                logs[key] = log_text

                preview = (log_text or "")[:200].replace("\n", " ")

                observation = f"Fetched logs for {key} (previous={previous}). Preview: \"{preview}...\""

                findings.setdefault("logs", {})[key] = log_text

        # --------------------------------------------------
        # SUMMARIZE
        # --------------------------------------------------

        elif action == "SUMMARIZE":

            summary = summarize_cluster(goal, findings)

            observation = "Summary generated successfully."

        # --------------------------------------------------
        # SEND SLACK
        # --------------------------------------------------

        elif action == "SEND_SLACK":

            print("\n==============================")
            print("FAKE SLACK MESSAGE")
            print("==============================")
            print(summary)
            print("==============================\n")

            observation = "Summary sent to Slack."

        # --------------------------------------------------
        # DONE
        # --------------------------------------------------

        elif action == "DONE":

            loops.append({

                "thought": thought,

                "action": action,

                "observation": "Workflow completed."

            })

            break

        # --------------------------------------------------
        # UNKNOWN
        # --------------------------------------------------

        else:

            observation = "Unknown action returned by planner."

        # --------------------------------------------------

        context.append({

            "action": action,

            "observation": observation

        })

        loops.append({

            "thought": thought,

            "action": action,

            "observation": observation

        })

    return {

        "loops": loops,

        "summary": summary,

        "findings": findings

    }
