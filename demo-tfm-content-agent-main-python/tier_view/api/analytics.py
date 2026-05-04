from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_user(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    return user, None


@require_http_methods(["GET"])
def get_analytics(request):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()

    news_res = admin.table("news_items").select("id", count="exact").eq("user_id", user["id"]).execute()
    total_news = news_res.count or 0

    interactions_res = admin.table("news_interactions").select("interaction").eq("user_id", user["id"]).execute()
    interactions = interactions_res.data or []
    saved = sum(1 for i in interactions if i["interaction"] == "saved")
    dismissed = sum(1 for i in interactions if i["interaction"] == "dismissed")
    used = sum(1 for i in interactions if i["interaction"] == "used")

    topic_scores_res = admin.table("user_topic_scores").select("topic,score").eq("user_id", user["id"]).execute()
    topic_data = topic_scores_res.data or []
    topic_data.sort(key=lambda x: x["score"], reverse=True)

    contents_res = admin.table("contents").select("format,status,created_at").eq("user_id", user["id"]).execute()
    contents = contents_res.data or []

    format_counts = {}
    for c in contents:
        fmt = c.get("format", "unknown")
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    return JsonResponse({
        "totalNews": total_news,
        "saved": saved,
        "dismissed": dismissed,
        "used": used,
        "topTopics": topic_data[:10],
        "totalContents": len(contents),
        "formatCounts": format_counts,
    })
