import json
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
def list_contents(request):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    status = request.GET.get("status")
    q = admin.table("contents").select("*").eq("user_id", user["id"]).order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    res = q.execute()
    return JsonResponse({"items": res.data or []})


@require_http_methods(["GET"])
def get_content(request, content_id):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    res = admin.table("contents").select("*").eq("id", content_id).eq("user_id", user["id"]).execute()
    if not res.data:
        return JsonResponse({"error": "Contenido no encontrado"}, status=404)
    return JsonResponse(res.data[0])


@csrf_exempt
@require_http_methods(["PATCH", "POST"])
def update_content(request, content_id):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    allowed = {"title", "body", "status", "metadata"}
    update_data = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not update_data:
        return JsonResponse({"error": "Nada que actualizar"}, status=400)

    admin = get_supabase_admin()
    res = (
        admin.table("contents")
        .update(update_data)
        .eq("id", content_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not res.data:
        return JsonResponse({"error": "Contenido no encontrado"}, status=404)
    return JsonResponse(res.data[0])


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def delete_content(request, content_id):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    admin.table("contents").delete().eq("id", content_id).eq("user_id", user["id"]).execute()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def duplicate_content(request, content_id):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    res = admin.table("contents").select("*").eq("id", content_id).eq("user_id", user["id"]).execute()
    if not res.data:
        return JsonResponse({"error": "Contenido no encontrado"}, status=404)

    original = res.data[0]
    new_data = {k: v for k, v in original.items() if k not in ("id", "created_at", "updated_at")}
    new_data["title"] = f"{original['title']} (copia)"
    new_data["status"] = "draft"
    dup = admin.table("contents").insert(new_data).execute()
    return JsonResponse(dup.data[0])


@require_http_methods(["GET"])
def list_saved_news(request):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    interactions_res = (
        admin.table("news_interactions")
        .select("news_item_id")
        .eq("user_id", user["id"])
        .eq("interaction", "saved")
        .execute()
    )
    ids = [row["news_item_id"] for row in (interactions_res.data or [])]
    if not ids:
        return JsonResponse({"items": []})
    news_res = admin.table("news_items").select("*").in_("id", ids).execute()
    return JsonResponse({"items": news_res.data or []})
