import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_admin(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    admin = get_supabase_admin()
    res = admin.table("user_roles").select("role").eq("user_id", user["id"]).eq("role", "admin").execute()
    if not res.data:
        return None, JsonResponse({"error": "Acceso restringido a administradores."}, status=403)
    return user, None


def _audit_log(admin_user, action, target_user_id="", payload=None, success=True, error=""):
    try:
        db = get_supabase_admin()
        db.table("admin_audit_logs").insert({
            "admin_id": admin_user["id"],
            "admin_email": admin_user["email"],
            "target_user_id": target_user_id,
            "action": action,
            "payload": payload or {},
            "result": "success" if success else "error",
            "success": success,
            "error_message": error,
        }).execute()
    except Exception:
        pass


@require_http_methods(["GET"])
def overview(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()

    users_res = admin.table("user_roles").select("user_id", count="exact").execute()
    total_users = users_res.count or 0

    contents_res = admin.table("contents").select("id", count="exact").execute()
    total_contents = contents_res.count or 0

    ai_res = admin.table("ai_usage_logs").select("estimated_cost_usd,success").execute()
    ai_logs = ai_res.data or []
    total_cost = sum(r.get("estimated_cost_usd", 0) for r in ai_logs if r.get("success"))
    total_errors = sum(1 for r in ai_logs if not r.get("success"))

    return JsonResponse({
        "totalUsers": total_users,
        "totalContents": total_contents,
        "totalAiCost": round(total_cost, 4),
        "totalErrors": total_errors,
    })


@require_http_methods(["GET"])
def list_users(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    res = admin.table("user_roles").select("*").order("user_id").limit(limit).offset(offset).execute()
    return JsonResponse({"users": res.data or []})


@require_http_methods(["GET"])
def list_contents(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("contents").select("*").order("created_at", desc=True).limit(50).execute()
    return JsonResponse({"contents": res.data or []})


@require_http_methods(["GET"])
def ai_logs(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("ai_usage_logs").select("*").order("created_at", desc=True).limit(100).execute()
    return JsonResponse({"logs": res.data or []})


@require_http_methods(["GET"])
def audit_logs(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("admin_audit_logs").select("*").order("created_at", desc=True).limit(100).execute()
    return JsonResponse({"logs": res.data or []})


@require_http_methods(["GET"])
def get_settings(request):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("settings").select("*").execute()
    return JsonResponse({"settings": {row["key"]: row["value"] for row in (res.data or [])}})


@csrf_exempt
@require_http_methods(["POST"])
def update_setting(request):
    admin_user, err = _require_admin(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    admin.table("settings").upsert({"key": body["key"], "value": body["value"]}, on_conflict="key").execute()
    _audit_log(admin_user, "update_settings", payload={"key": body["key"]})
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def ban_user(request):
    admin_user, err = _require_admin(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    admin.table("user_bans").upsert({"user_id": body["user_id"], "reason": body.get("reason", "")}, on_conflict="user_id").execute()
    _audit_log(admin_user, "ban_user", target_user_id=body["user_id"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def unban_user(request):
    admin_user, err = _require_admin(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    admin.table("user_bans").delete().eq("user_id", body["user_id"]).execute()
    _audit_log(admin_user, "unban_user", target_user_id=body["user_id"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def set_admin(request):
    admin_user, err = _require_admin(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    if body.get("is_admin"):
        admin.table("user_roles").upsert({"user_id": body["user_id"], "role": "admin"}, on_conflict="user_id").execute()
    else:
        admin.table("user_roles").update({"role": "user"}).eq("user_id", body["user_id"]).execute()
    _audit_log(admin_user, "set_admin", target_user_id=body["user_id"], payload={"is_admin": body.get("is_admin")})
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def set_quota(request):
    admin_user, err = _require_admin(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    admin.table("user_quotas").upsert({
        "user_id": body["user_id"],
        "daily_content_limit": body.get("daily_content_limit", 50),
        "daily_image_limit": body.get("daily_image_limit", 20),
        "monthly_content_limit": body.get("monthly_content_limit", 500),
    }, on_conflict="user_id").execute()
    _audit_log(admin_user, "set_quota", target_user_id=body["user_id"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def admin_delete_content(request, content_id):
    admin_user, err = _require_admin(request)
    if err:
        return err
    admin = get_supabase_admin()
    admin.table("contents").delete().eq("id", content_id).execute()
    _audit_log(admin_user, "delete_content", payload={"content_id": content_id})
    return JsonResponse({"ok": True})
