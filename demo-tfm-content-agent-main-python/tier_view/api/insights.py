from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tier_business.ai_service import call_ai_sync
from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_user(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    return user, None


@csrf_exempt
@require_http_methods(["POST"])
def generate_insights(request):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()

    news_res = (
        admin.table("news_items")
        .select("title,topic,summary")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    recent_news = news_res.data or []

    scores_res = admin.table("user_topic_scores").select("topic,score").eq("user_id", user["id"]).execute()
    topic_scores = scores_res.data or []

    context_lines = ["Tendencias recientes del usuario:"]
    for item in recent_news[:10]:
        context_lines.append(f"- [{item.get('topic','?')}] {item.get('title','')}")
    if topic_scores:
        context_lines.append("\nTopics con más interacciones:")
        for ts in sorted(topic_scores, key=lambda x: x["score"], reverse=True)[:5]:
            context_lines.append(f"- {ts['topic']}: {ts['score']:.1f} puntos")

    context = "\n".join(context_lines)

    try:
        result = call_ai_sync(
            format="insights",
            topic="análisis de tendencias del creador de contenido",
            tone="estratégico y directo",
            context=context,
        )
        return JsonResponse({
            "structured": result["structured"],
            "content": result["content"],
            "model": result["model"],
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
