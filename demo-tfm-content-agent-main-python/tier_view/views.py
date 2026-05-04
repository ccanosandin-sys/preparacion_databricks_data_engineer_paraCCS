from django.shortcuts import render, redirect

from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _is_admin(user_id: str) -> bool:
    try:
        admin = get_supabase_admin()
        res = admin.table("user_roles").select("role").eq("user_id", user_id).eq("role", "admin").execute()
        return bool(res.data)
    except Exception:
        return False


def _auth_context(request):
    user = get_current_user(request)
    if not user:
        return None, redirect("/auth/login")
    ctx = {"user": user, "is_admin": _is_admin(user["id"])}
    return ctx, None


def landing(request):
    return render(request, "index.html", {})


def dashboard(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "dashboard.html", {**ctx, "active_page": "dashboard"})


def create_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "create.html", {**ctx, "active_page": "create"})


def library_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "library.html", {**ctx, "active_page": "library"})


def trends_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "trends.html", {**ctx, "active_page": "trends"})


def analytics_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "analytics.html", {**ctx, "active_page": "analytics"})


def insights_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "insights.html", {**ctx, "active_page": "insights"})


def brand_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "brand.html", {**ctx, "active_page": "brand"})


def team_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "team.html", {**ctx, "active_page": "team"})


def settings_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    return render(request, "settings.html", {**ctx, "active_page": "settings"})


def admin_page(request):
    ctx, redir = _auth_context(request)
    if redir:
        return redir
    if not ctx["is_admin"]:
        return redirect("/dashboard")
    return render(request, "admin.html", {**ctx, "active_page": "admin"})


def not_found_page(request, exception=None):
    return render(request, "notfound.html", {}, status=404)
