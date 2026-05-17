from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from lookingglass.services import LookingGlassError, get_looking_glass_snapshot, get_refresh_seconds

from .forms import PublicRegistrationForm
from .models import ParticipantRegistration, User


class PortalLoginView(LoginView):
    template_name = "pages/login.html"

    def get_success_url(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return reverse("admin_hub")
        return reverse("dashboard")


def home(request):
    return render(request, "pages/home.html")


@login_required
def dashboard(request):
    route_server_keys = ("rs1", "rs2")
    snapshot_map = {"ipv4": {}, "ipv6": {}}
    errors: list[str] = []

    for rs_key in route_server_keys:
        for afi in ("ipv4", "ipv6"):
            try:
                snapshot_map[afi][rs_key] = get_looking_glass_snapshot(rs_key=rs_key, afi=afi, query="")
            except LookingGlassError as exc:
                errors.append(f"{rs_key.upper()} {afi.upper()}: {exc}")

    ipv4_snapshots = [snap for snap in snapshot_map["ipv4"].values() if snap]
    ipv6_snapshots = [snap for snap in snapshot_map["ipv6"].values() if snap]

    combined_summary_rows: list[dict] = []
    combined_routes_ipv4: list[dict] = []
    combined_routes_ipv6: list[dict] = []
    route_server_status: list[dict] = []

    for rs_key in route_server_keys:
        ipv4_snapshot = snapshot_map["ipv4"].get(rs_key)
        ipv6_snapshot = snapshot_map["ipv6"].get(rs_key)

        if ipv4_snapshot:
            for row in ipv4_snapshot["summary"]:
                combined_summary_rows.append(
                    {
                        "route_server": ipv4_snapshot["route_server"].label,
                        "peer_asn": row.get("asn", "-"),
                        "peer_ip": row.get("neighbor", "-"),
                        "state": row.get("state", "Unknown"),
                        "uptime": row.get("uptime", "-"),
                        "prefixes": row.get("prefixes", 0),
                        "msg_received": row.get("msg_received", 0),
                        "msg_sent": row.get("msg_sent", 0),
                    }
                )
            combined_routes_ipv4.extend(ipv4_snapshot["routes"])

        if ipv6_snapshot:
            combined_routes_ipv6.extend(ipv6_snapshot["routes"])

        daemon_source = ipv4_snapshot or ipv6_snapshot
        if daemon_source:
            route_server_status.append(
                {
                    "name": daemon_source["route_server"].label,
                    "is_running": daemon_source["daemon_status"]["is_running"],
                    "active_line": daemon_source["daemon_status"]["active_line"],
                    "peer_count": daemon_source["stats"]["peer_count"],
                    "route_count": daemon_source["stats"]["route_count"],
                }
            )
        else:
            route_server_status.append(
                {
                    "name": "Route Server 1" if rs_key == "rs1" else "Route Server 2",
                    "is_running": False,
                    "active_line": "Unavailable",
                    "peer_count": 0,
                    "route_count": 0,
                }
            )

    established_count = sum(1 for row in combined_summary_rows if str(row.get("state", "")).lower() == "established")
    idle_count = max(0, len(combined_summary_rows) - established_count)

    # Aggregate advertised prefixes from peer summaries (State/PfxRcd-derived).
    ipv4_prefix_total = sum(int(row.get("prefixes", 0) or 0) for snap in ipv4_snapshots for row in snap["summary"])
    ipv6_prefix_total = sum(int(row.get("prefixes", 0) or 0) for snap in ipv6_snapshots for row in snap["summary"])

    banner_ok = established_count > 0 and not errors
    banner_text = "BGP Session Established" if banner_ok else "BGP Session Degraded"

    context = {
        "banner_ok": banner_ok,
        "banner_text": banner_text,
        "errors": errors,
        "refresh_seconds": get_refresh_seconds(),
        "established_count": established_count,
        "idle_count": idle_count,
        "peer_total": len(combined_summary_rows),
        "active_peer_count": established_count,
        "prefixes_total": ipv4_prefix_total + ipv6_prefix_total,
        "prefixes_ipv4_total": ipv4_prefix_total,
        "prefixes_ipv6_total": ipv6_prefix_total,
        "bgp_sessions": combined_summary_rows,
        "top_ipv4_routes": combined_routes_ipv4[:8],
        "top_ipv6_routes": combined_routes_ipv6[:8],
        "route_server_status": route_server_status,
    }
    return render(request, "pages/dashboard.html", context)


def register(request):
    if request.method == 'POST':
        form = PublicRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data['email'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        role=User.Role.PARTICIPANT,
                        is_active=False,
                        email_verified=False,
                    )
                    ParticipantRegistration.objects.create(user=user, **form.participant_data())
            except IntegrityError:
                form.add_error(None, 'A registration already exists for this email or ASN.')
            else:
                messages.success(request, 'Application submitted. Await admin approval.')
                return redirect('login')
    else:
        form = PublicRegistrationForm()

    return render(request, 'pages/register.html', {'form': form})


def documentation(request):
    return render(request, 'pages/documentation.html')


@login_required
def peer_matrix(request):
    return render(request, 'pages/peer_matrix.html')


@login_required
def admin_hub(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Admin access required.")
        return redirect("dashboard")
    return render(request, "pages/admin_hub.html")
