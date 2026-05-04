import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tier_business.ai_service import call_ai_sync
from tier_business.quota_service import check_quota, log_ai_usage
from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_user(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    return user, None


@csrf_exempt
@require_http_methods(["POST"])
def generate_content(request):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    topic = body.get("topic", "")
    fmt = body.get("format", "")
    tone = body.get("tone", "profesional")
    boost = body.get("boost", "")
    context = body.get("context", "")

    if not topic or not fmt:
        return JsonResponse({"error": "topic y format son obligatorios"}, status=400)

    quota = check_quota(user["id"], kind="content")
    if not quota["allowed"]:
        return JsonResponse({"error": quota["reason"]}, status=429)

    try:
        result = call_ai_sync(format=fmt, topic=topic, tone=tone, boost=boost, context=context)
        log_ai_usage(
            user_id=user["id"],
            function_name="generate-content",
            model=result["model"],
            kind="content",
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
            estimated_cost=result["estimated_cost"],
            success=True,
            metadata={"format": fmt, "topic": topic},
        )
        return JsonResponse({
            "format": result["format"],
            "structured": result["structured"],
            "content": result["content"],
            "model": result["model"],
        })
    except Exception as e:
        log_ai_usage(
            user_id=user["id"],
            function_name="generate-content",
            model="unknown",
            kind="content",
            tokens_in=0,
            tokens_out=0,
            estimated_cost=0,
            success=False,
            error_message=str(e),
        )
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_content(request):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    admin = get_supabase_admin()
    res = admin.table("contents").insert({
        "user_id": user["id"],
        "title": body.get("title", ""),
        "body": body.get("body", ""),
        "format": body.get("format", ""),
        "topic": body.get("topic", ""),
        "tone": body.get("tone", ""),
        "status": body.get("status", "draft"),
        "metadata": body.get("metadata") or {},
        "source_news_id": body.get("source_news_id"),
    }).execute()

    if not res.data:
        return JsonResponse({"error": "Error guardando contenido"}, status=500)
    return JsonResponse(res.data[0])
