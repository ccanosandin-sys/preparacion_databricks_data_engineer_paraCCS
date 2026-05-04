import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tier_business.news_service import fetch_news_rss_sync, rank_news, get_top_topics, build_boost_prompt
from tier_business.ai_service import enrich_news_with_ai_sync
from tier_business.supabase_client import get_supabase_admin
from tier_view.auth_views import get_current_user


def _require_user(request):
    user = get_current_user(request)
    if not user:
        return None, JsonResponse({"error": "No autenticado"}, status=401)
    return user, None


@csrf_exempt
@require_http_methods(["POST"])
def fetch_news(request):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    niche = body.get("niche", "")
    lang = body.get("lang", "es")

    raw_items = fetch_news_rss_sync(niche, lang)
    enriched = enrich_news_with_ai_sync(raw_items)

    admin = get_supabase_admin()
    saved = []
    for item in enriched:
        if not item.get("source_url"):
            continue
        try:
            res = admin.table("news_items").upsert(
                {
                    "user_id": user["id"],
                    "title": item["title"],
                    "summary": item.get("summary", ""),
                    "topic": item.get("topic", "otro"),
                    "source_url": item["source_url"],
                    "source_name": item.get("source_name", ""),
                    "published_at": item.get("published_at"),
                    "language": lang,
                },
                on_conflict="user_id,source_url",
            ).execute()
            if res.data:
                saved.extend(res.data)
        except Exception:
            continue

    return JsonResponse({"items": saved, "count": len(saved)})


@require_http_methods(["GET"])
def rank_news_view(request):
    user, err = _require_user(request)
    if err:
        return err

    admin = get_supabase_admin()
    news_res = admin.table("news_items").select("*").eq("user_id", user["id"]).order("published_at", desc=True).limit(50).execute()
    items = news_res.data or []

    scores_res = admin.table("user_topic_scores").select("topic,score").eq("user_id", user["id"]).execute()
    topic_scores = {row["topic"]: row["score"] for row in (scores_res.data or [])}

    ranked = rank_news(items, topic_scores)
    top_topics = get_top_topics(topic_scores)
    boost_prompt = build_boost_prompt(top_topics)

    return JsonResponse({
        "items": ranked,
        "topTopics": top_topics,
        "boostPrompt": boost_prompt,
    })


@csrf_exempt
@require_http_methods(["POST"])
def news_interaction(request):
    user, err = _require_user(request)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    news_item_id = body.get("news_item_id", "")
    interaction = body.get("interaction", "")
    admin = get_supabase_admin()

    existing = (
        admin.table("news_interactions")
        .select("id,interaction")
        .eq("user_id", user["id"])
        .eq("news_item_id", news_item_id)
        .execute()
    )

    if existing.data:
        admin.table("news_interactions").update({"interaction": interaction}).eq("id", existing.data[0]["id"]).execute()
    else:
        admin.table("news_interactions").insert({
            "user_id": user["id"],
            "news_item_id": news_item_id,
            "interaction": interaction,
        }).execute()

    news_res = admin.table("news_items").select("topic").eq("id", news_item_id).execute()
    if news_res.data:
        topic = news_res.data[0].get("topic", "otro")
        score_delta = {"saved": 1.0, "used": 2.0, "dismissed": -0.5}.get(interaction, 0)
        if score_delta != 0:
            existing_score = (
                admin.table("user_topic_scores")
                .select("score")
                .eq("user_id", user["id"])
                .eq("topic", topic)
                .execute()
            )
            if existing_score.data:
                new_score = max(0, existing_score.data[0]["score"] + score_delta)
                admin.table("user_topic_scores").update({"score": new_score}).eq("user_id", user["id"]).eq("topic", topic).execute()
            else:
                admin.table("user_topic_scores").insert({
                    "user_id": user["id"],
                    "topic": topic,
                    "score": max(0, score_delta),
                }).execute()

    return JsonResponse({"ok": True})
