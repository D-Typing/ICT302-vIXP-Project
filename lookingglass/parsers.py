import ipaddress
import re


def _safe_int(value: str, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _is_prefix(token: str) -> bool:
    if "/" not in token:
        return False
    try:
        ipaddress.ip_network(token, strict=False)
        return True
    except ValueError:
        return False


def parse_bgp_summary(output: str) -> list[dict]:
    peers: list[dict] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Neighbor") or stripped.startswith("Total number"):
            continue
        if "BGP table version" in stripped or "router identifier" in stripped:
            continue
        if not re.match(r"^[0-9a-fA-F:.]+", stripped):
            continue

        parts = stripped.split()
        if len(parts) < 9:
            continue

        state_field = " ".join(parts[9:]) if len(parts) > 9 else parts[8]
        prefixes = None
        state = state_field
        if parts[8].isdigit():
            state = "Established"
            prefixes = _safe_int(parts[8], 0)
        elif state_field.isdigit():
            state = "Established"
            prefixes = _safe_int(state_field, 0)

        peers.append(
            {
                "neighbor": parts[0],
                "asn": parts[2],
                "msg_received": _safe_int(parts[3]),
                "msg_sent": _safe_int(parts[4]),
                "uptime": parts[8],
                "state": state,
                "prefixes": prefixes if prefixes is not None else 0,
            }
        )
    return peers


def parse_bgp_routes(output: str) -> list[dict]:
    routes: list[dict] = []
    for line in output.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.lstrip().startswith(
            (
                "BGP routing table",
                "Status codes:",
                "Origin codes:",
                "RPKI validation",
                "Displayed",
                "Total number of prefixes",
                "Network",
            )
        ):
            continue
        if "Next Hop" in stripped and "Path" in stripped:
            continue

        parts = stripped.split()
        prefix_index = -1
        for idx, token in enumerate(parts):
            if _is_prefix(token):
                prefix_index = idx
                break
        if prefix_index == -1 or prefix_index >= len(parts) - 1:
            continue

        status = "".join(parts[:prefix_index]).strip()
        prefix = parts[prefix_index]
        next_hop = parts[prefix_index + 1]
        remainder = parts[prefix_index + 2 :]

        numeric_fields: list[str] = []
        as_path_tokens: list[str] = []
        for token in remainder:
            if token.isdigit() and len(numeric_fields) < 3:
                numeric_fields.append(token)
            else:
                as_path_tokens.append(token)

        metric = numeric_fields[0] if len(numeric_fields) > 0 else "-"
        local_pref = numeric_fields[1] if len(numeric_fields) > 1 else "-"
        weight = numeric_fields[2] if len(numeric_fields) > 2 else "-"
        as_path = " ".join(as_path_tokens).strip() or "-"

        routes.append(
            {
                "status": status or "-",
                "prefix": prefix,
                "next_hop": next_hop,
                "metric": metric,
                "local_pref": local_pref,
                "weight": weight,
                "as_path": as_path,
                "age": "-",
            }
        )

    return routes


def parse_bgp_neighbors(output: str) -> list[dict]:
    blocks = re.split(r"\n(?=BGP neighbor is )", output)
    neighbors: list[dict] = []

    for block in blocks:
        if not block.strip().startswith("BGP neighbor is"):
            continue

        neighbor_match = re.search(r"BGP neighbor is\s+([0-9a-fA-F:.]+),\s+remote AS\s+(\d+)", block)
        if not neighbor_match:
            continue

        state_match = re.search(r"BGP state =\s*([^,\n]+),\s*up for\s*([^\n]+)", block)
        state = state_match.group(1).strip() if state_match else "Unknown"
        uptime = state_match.group(2).strip() if state_match else "-"

        accepted_match = re.search(r"(\d+)\s+accepted prefixes", block)
        received_match = re.search(r"Prefixes Current:\s+(\d+)", block)
        advertised_match = re.search(r"Advertised prefixes:\s+(\d+)", block)

        neighbors.append(
            {
                "neighbor": neighbor_match.group(1),
                "peer_asn": neighbor_match.group(2),
                "session_state": state,
                "uptime": uptime,
                "received_prefixes": _safe_int(received_match.group(1), 0) if received_match else 0,
                "advertised_prefixes": _safe_int(advertised_match.group(1), 0) if advertised_match else 0,
                "accepted_prefixes": _safe_int(accepted_match.group(1), 0) if accepted_match else 0,
            }
        )

    return neighbors


def parse_daemon_status(output: str) -> dict:
    active_line = ""
    for line in output.splitlines():
        if "Active:" in line:
            active_line = line.strip()
            break

    is_running = "active (running)" in active_line.lower()
    return {
        "is_running": is_running,
        "active_line": active_line or "Active status unavailable",
        "raw": output.strip(),
    }
