import json
from datetime import datetime, timezone, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_user(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    return user, None


@require_http_methods(["GET"])
def list_members(request):
    user, err = _require_user(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("team_members").select("*").eq("owner_id", user["id"]).execute()
    return JsonResponse({"members": res.data or []})


@require_http_methods(["GET"])
def list_invitations(request):
    user, err = _require_user(request)
    if err:
        return err
    admin = get_supabase_admin()
    res = admin.table("team_invitations").select("*").eq("owner_id", user["id"]).execute()
    return JsonResponse({"invitations": res.data or []})


@csrf_exempt
@require_http_methods(["POST"])
def invite_member(request):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    email = body.get("email", "")
    role = body.get("role", "editor")
    admin = get_supabase_admin()

    existing = (
        admin.table("team_invitations")
        .select("id,status")
        .eq("owner_id", user["id"])
        .eq("email", email)
        .eq("status", "pending")
        .execute()
    )
    if existing.data:
        return JsonResponse({"error": "Ya existe una invitación pendiente para este email."}, status=409)

    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    res = admin.table("team_invitations").insert({
        "owner_id": user["id"],
        "email": email,
        "role": role,
        "status": "pending",
        "expires_at": expires_at,
    }).execute()
    return JsonResponse(res.data[0])


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def revoke_invitation(request, invitation_id):
    user, err = _require_user(request)
    if err:
        return err
    admin = get_supabase_admin()
    admin.table("team_invitations").update({"status": "revoked"}).eq("id", invitation_id).eq("owner_id", user["id"]).execute()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["PATCH", "POST"])
def update_member(request, member_id):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    res = (
        admin.table("team_members")
        .update({"role": body.get("role", "editor")})
        .eq("id", member_id)
        .eq("owner_id", user["id"])
        .execute()
    )
    if not res.data:
        return JsonResponse({"error": "Miembro no encontrado"}, status=404)
    return JsonResponse(res.data[0])


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def remove_member(request, member_id):
    user, err = _require_user(request)
    if err:
        return err
    admin = get_supabase_admin()
    admin.table("team_members").delete().eq("id", member_id).eq("owner_id", user["id"]).execute()
    return JsonResponse({"ok": True})
