import json
import paramiko

# ── VM connection details ──────────────────────────────────────────
ROUTE_SERVERS = {
    'RS1': {
        'host': '151.158.219.194',
        'user': 'declan00',
        'key_path': '/home/youruser/.ssh/ixp_key',
    },
    'RS2': {
        'host': '151.158.219.195',
        'user': 'declan00',
        'key_path': '/home/youruser/.ssh/ixp_key',
    },
}


def run_vtysh(rs_name, command):
    """
    SSHs into the given route server VM and runs a vtysh command.
    Returns parsed JSON or None on failure.
    """
    rs = ROUTE_SERVERS.get(rs_name)
    if not rs:
        print(f"[FRR] Unknown route server: {rs_name}")
        return None

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            rs['host'],
            username=rs['user'],
            key_filename=rs['key_path'],
            timeout=10,
        )
        stdin, stdout, stderr = client.exec_command(f'vtysh -c "{command}"')
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        client.close()

        if error:
            print(f"[FRR:{rs_name}] vtysh stderr: {error}")

        return json.loads(output)

    except json.JSONDecodeError as e:
        print(f"[FRR:{rs_name}] JSON parse error: {e}")
        return None
    except paramiko.AuthenticationException:
        print(f"[FRR:{rs_name}] SSH authentication failed — check key path and user")
        return None
    except Exception as e:
        print(f"[FRR:{rs_name}] Connection error: {e}")
        return None


def get_bgp_summary_ipv4(rs_name):
    return run_vtysh(rs_name, "show bgp ipv4 unicast summary json")


def get_bgp_summary_ipv6(rs_name):
    return run_vtysh(rs_name, "show bgp ipv6 unicast summary json")


def get_advertised_routes(rs_name, peer_ip, family='ipv4'):
    cmd = f"show bgp {family} unicast neighbors {peer_ip} advertised-routes json"
    data = run_vtysh(rs_name, cmd)
    if data:
        return data.get('totalPrefixCounter', 0)
    return 0


def get_all_bgp_data():
    """
    Queries both route servers and returns a combined dict:
    {
        'RS1': {'ipv4': {...peers...}, 'ipv6': {...peers...}},
        'RS2': {'ipv4': {...peers...}, 'ipv6': {...peers...}},
    }
    """
    results = {}
    for rs_name in ROUTE_SERVERS:
        ipv4_data = get_bgp_summary_ipv4(rs_name)
        ipv6_data = get_bgp_summary_ipv6(rs_name)

        results[rs_name] = {
            'ipv4': ipv4_data.get('ipv4Unicast', {}).get('peers', {}) if ipv4_data else {},
            'ipv6': ipv6_data.get('ipv6Unicast', {}).get('peers', {}) if ipv6_data else {},
        }
    return results
