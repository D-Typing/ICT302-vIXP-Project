import os
from dataclasses import dataclass
from pathlib import Path

import paramiko
from django.core.cache import cache
from django.utils import timezone
from dotenv import load_dotenv

from .parsers import parse_bgp_neighbors, parse_bgp_routes, parse_bgp_summary, parse_daemon_status
from .utils import clamp, env_int, ensure_env_file, filter_records

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ensure_env_file(BASE_DIR)
load_dotenv(ENV_PATH)


class LookingGlassError(Exception):
    pass


@dataclass(frozen=True)
class RouteServer:
    key: str
    label: str
    host: str


ALLOWED_COMMANDS = {
    "ipv4_summary": 'sudo vtysh -c "show ip bgp summary"',
    "ipv4_routes": 'sudo vtysh -c "show ip bgp"',
    "ipv6_summary": 'sudo vtysh -c "show bgp ipv6 summary"',
    "ipv6_routes": 'sudo vtysh -c "show bgp ipv6"',
    "neighbors": 'sudo vtysh -c "show ip bgp neighbors"',
    "daemon_status": "sudo systemctl status frr",
}


def _route_servers() -> dict[str, RouteServer]:
    return {
        "rs1": RouteServer(key="rs1", label="Route Server 1", host=os.environ.get("VM1_HOST", "").strip()),
        "rs2": RouteServer(key="rs2", label="Route Server 2", host=os.environ.get("VM2_HOST", "").strip()),
    }


def get_route_servers() -> list[RouteServer]:
    return [server for server in _route_servers().values() if server.host]


def resolve_route_server(rs_key: str) -> RouteServer:
    catalog = _route_servers()
    if rs_key in catalog and catalog[rs_key].host:
        return catalog[rs_key]
    if catalog["rs1"].host:
        return catalog["rs1"]
    if catalog["rs2"].host:
        return catalog["rs2"]
    raise LookingGlassError("No route server host configured. Check VM1_HOST/VM2_HOST in .env.")


def _cache_ttl() -> int:
    return clamp(env_int("LG_CACHE_TTL_SECONDS", 20), 5, 120)


def get_refresh_seconds() -> int:
    return clamp(env_int("LG_REFRESH_SECONDS", 45), 30, 60)


def _ssh_connection_settings() -> dict:
    username = os.environ.get("VM_USERNAME", "").strip()
    password = os.environ.get("VM_PASSWORD", "")
    if not username or not password:
        raise LookingGlassError("VM_USERNAME or VM_PASSWORD is missing in .env.")

    return {
        "username": username,
        "password": password,
        "timeout": clamp(env_int("LG_SSH_CONNECT_TIMEOUT", 10), 3, 60),
        "banner_timeout": clamp(env_int("LG_SSH_BANNER_TIMEOUT", 10), 3, 60),
        "auth_timeout": clamp(env_int("LG_SSH_AUTH_TIMEOUT", 10), 3, 60),
        "command_timeout": clamp(env_int("LG_SSH_COMMAND_TIMEOUT", 20), 5, 120),
    }


def _run_command(client: paramiko.SSHClient, command_key: str, sudo_password: str, command_timeout: int) -> str:
    if command_key not in ALLOWED_COMMANDS:
        raise LookingGlassError(f"Command '{command_key}' is not allowed.")

    base_command = ALLOWED_COMMANDS[command_key]
    non_interactive_command = base_command.replace("sudo ", "sudo -n ", 1)

    stdin, stdout, stderr = client.exec_command(non_interactive_command, timeout=command_timeout)
    exit_code = stdout.channel.recv_exit_status()
    standard_output = stdout.read().decode("utf-8", errors="replace")
    standard_error = stderr.read().decode("utf-8", errors="replace")
    if exit_code == 0:
        return standard_output

    # Fallback for environments where sudo still requires a password.
    if "sudo" in base_command:
        sudo_password_command = base_command.replace("sudo ", "sudo -S -p '' ", 1)
        stdin, stdout, stderr = client.exec_command(sudo_password_command, timeout=command_timeout)
        stdin.write(sudo_password + "\n")
        stdin.flush()
        exit_code = stdout.channel.recv_exit_status()
        standard_output = stdout.read().decode("utf-8", errors="replace")
        standard_error = stderr.read().decode("utf-8", errors="replace")
        if exit_code == 0:
            return standard_output

    raise LookingGlassError(f"Command '{command_key}' failed: {standard_error.strip() or 'unknown error'}")


def _fetch_live_data(route_server: RouteServer, afi: str) -> dict:
    ssh_cfg = _ssh_connection_settings()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=route_server.host,
            username=ssh_cfg["username"],
            password=ssh_cfg["password"],
            look_for_keys=False,
            allow_agent=False,
            timeout=ssh_cfg["timeout"],
            banner_timeout=ssh_cfg["banner_timeout"],
            auth_timeout=ssh_cfg["auth_timeout"],
        )

        summary_key = "ipv6_summary" if afi == "ipv6" else "ipv4_summary"
        routes_key = "ipv6_routes" if afi == "ipv6" else "ipv4_routes"

        raw_summary = _run_command(ssh, summary_key, ssh_cfg["password"], ssh_cfg["command_timeout"])
        raw_routes = _run_command(ssh, routes_key, ssh_cfg["password"], ssh_cfg["command_timeout"])
        raw_neighbors = _run_command(ssh, "neighbors", ssh_cfg["password"], ssh_cfg["command_timeout"])
        raw_daemon = _run_command(ssh, "daemon_status", ssh_cfg["password"], ssh_cfg["command_timeout"])
    except paramiko.AuthenticationException as exc:
        raise LookingGlassError(f"SSH authentication failed for {route_server.label}.") from exc
    except paramiko.SSHException as exc:
        raise LookingGlassError(f"SSH error while talking to {route_server.label}: {exc}") from exc
    except TimeoutError as exc:
        raise LookingGlassError(f"SSH timeout while talking to {route_server.label}.") from exc
    finally:
        ssh.close()

    summary_rows = parse_bgp_summary(raw_summary)
    route_rows = parse_bgp_routes(raw_routes)
    neighbor_rows = parse_bgp_neighbors(raw_neighbors)
    daemon_status = parse_daemon_status(raw_daemon)

    return {
        "summary": summary_rows,
        "routes": route_rows,
        "neighbors": neighbor_rows,
        "daemon_status": daemon_status,
        "raw": {
            "summary": raw_summary,
            "routes": raw_routes,
            "neighbors": raw_neighbors,
            "daemon_status": raw_daemon,
        },
    }


def get_looking_glass_snapshot(rs_key: str, afi: str = "ipv4", query: str = "") -> dict:
    route_server = resolve_route_server(rs_key)
    normalized_afi = "ipv6" if afi == "ipv6" else "ipv4"
    cache_key = f"lookingglass:{route_server.key}:{normalized_afi}"
    payload = cache.get(cache_key)

    if payload is None:
        payload = _fetch_live_data(route_server, normalized_afi)
        cache.set(cache_key, payload, _cache_ttl())

    summary_rows = payload["summary"]
    route_rows = payload["routes"]
    neighbor_rows = payload["neighbors"]
    if query:
        summary_rows = filter_records(summary_rows, query, ("neighbor", "asn", "state"))
        route_rows = filter_records(route_rows, query, ("prefix", "next_hop", "as_path"))
        neighbor_rows = filter_records(neighbor_rows, query, ("neighbor", "peer_asn", "session_state"))

    established_peers = sum(1 for row in payload["summary"] if row.get("state", "").lower() == "established")
    accepted_routes = sum(1 for row in payload["routes"] if "*" in str(row.get("status", "")))

    return {
        "route_server": route_server,
        "afi": normalized_afi,
        "query": query,
        "summary": summary_rows,
        "routes": route_rows,
        "neighbors": neighbor_rows,
        "daemon_status": payload["daemon_status"],
        "stats": {
            "peer_count": len(payload["summary"]),
            "established_peers": established_peers,
            "route_count": len(payload["routes"]),
            "accepted_route_count": accepted_routes,
        },
        "last_refresh": timezone.now(),
        "refresh_seconds": get_refresh_seconds(),
    }
