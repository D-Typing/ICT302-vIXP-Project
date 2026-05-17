from django.shortcuts import redirect, render

from .services import LookingGlassError, get_looking_glass_snapshot, get_route_servers


def _requested_route_server(request) -> str:
    return request.GET.get("rs", "rs1").strip().lower()


def _requested_afi(request) -> str:
    return "ipv6" if request.GET.get("afi", "ipv4").strip().lower() == "ipv6" else "ipv4"


def _requested_query(request) -> str:
    return request.GET.get("q", "").strip()


def _build_context(request, active_page: str) -> dict:
    rs_key = _requested_route_server(request)
    afi = _requested_afi(request)
    query = _requested_query(request)
    context = {
        "active_page": active_page,
        "route_servers": get_route_servers(),
        "selected_rs": rs_key,
        "selected_afi": afi,
        "search_query": query,
    }

    try:
        context["snapshot"] = get_looking_glass_snapshot(rs_key=rs_key, afi=afi, query=query)
        context["error_message"] = ""
    except LookingGlassError as exc:
        context["snapshot"] = None
        context["error_message"] = str(exc)

    return context


def index(request):
    return redirect("lookingglass:summary")


def summary(request):
    context = _build_context(request, "summary")
    return render(request, "lookingglass/summary.html", context)


def routes(request):
    context = _build_context(request, "routes")
    return render(request, "lookingglass/routes.html", context)


def neighbors(request):
    context = _build_context(request, "neighbors")
    return render(request, "lookingglass/neighbors.html", context)
