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
def get_profile(request):
    user, err = _require_user(request)
    if err:
        return err
    admin = get_supabase_admin()
    try:
        res = admin.table("profiles").select("*").eq("id", user["id"]).execute()
        if not res.data:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        return JsonResponse(res.data[0])
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def update_profile(request):
    user, err = _require_user(request)
    if err:
        return err
    try:
        profile_data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    try:
        admin.table("profiles").update(profile_data).eq("id", user["id"]).execute()
        return JsonResponse({"message": "Perfil actualizado"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def update_preferences(request):
    user, err = _require_user(request)
    if err:
        return err
    try:
        preferences = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    try:
        admin.table("user_preferences").upsert({"user_id": user["id"], **preferences}).execute()
        return JsonResponse({"message": "Preferencias actualizadas"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
