from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from tier_business.supabase_client import get_supabase


def get_current_user(request):
    return request.session.get("user")


def require_auth(request):
    user = request.session.get("user")
    if not user:
        return None, redirect("/auth/login")
    return user, None


@require_http_methods(["GET"])
def login_page(request):
    if get_current_user(request):
        return redirect("/dashboard")
    return render(request, "auth.html", {"mode": "login", "error": None})


@require_http_methods(["GET"])
def signup_page(request):
    if get_current_user(request):
        return redirect("/dashboard")
    return render(request, "auth.html", {"mode": "signup", "error": None})


@csrf_protect
@require_http_methods(["POST"])
def login_post(request):
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = result.user
        session = result.session
        request.session["user"] = {
            "id": user.id,
            "email": user.email,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        }
        return redirect("/dashboard")
    except Exception as e:
        return render(request, "auth.html", {"mode": "login", "error": str(e)})


@csrf_protect
@require_http_methods(["POST"])
def signup_post(request):
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
        if result.user and not result.session:
            return render(request, "auth.html", {
                "mode": "signup",
                "error": None,
                "info": "Revisa tu email para confirmar tu cuenta.",
            })
        if result.session:
            user = result.user
            session = result.session
            request.session["user"] = {
                "id": user.id,
                "email": user.email,
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
            }
            return redirect("/dashboard")
        return render(request, "auth.html", {"mode": "signup", "error": "Error al registrarse."})
    except Exception as e:
        return render(request, "auth.html", {"mode": "signup", "error": str(e)})


@require_http_methods(["GET"])
def logout(request):
    request.session.flush()
    return redirect("/auth/login")
