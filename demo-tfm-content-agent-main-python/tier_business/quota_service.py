from datetime import date
from typing import Any
from tier_business.supabase_client import get_supabase_admin

DEFAULT_DAILY_CONTENT = 50
DEFAULT_DAILY_IMAGE = 20
DEFAULT_MONTHLY_CONTENT = 500


def check_quota(user_id: str, kind: str = "content") -> dict[str, Any]:
    admin = get_supabase_admin()
    today = date.today().isoformat()

    ban_res = admin.table("user_bans").select("user_id").eq("user_id", user_id).execute()
    if ban_res.data:
        return {"allowed": False, "reason": "Tu cuenta está suspendida."}

    quota_res = admin.table("user_quotas").select("*").eq("user_id", user_id).execute()
    quota = quota_res.data[0] if quota_res.data else {}

    if kind == "content":
        daily_limit = quota.get("daily_content_limit", DEFAULT_DAILY_CONTENT)
    else:
        daily_limit = quota.get("daily_image_limit", DEFAULT_DAILY_IMAGE)

    usage_res = (
        admin.table("ai_usage_logs")
        .select("id")
        .eq("user_id", user_id)
        .eq("kind", kind)
        .eq("success", True)
        .gte("created_at", f"{today}T00:00:00")
        .execute()
    )
    daily_used = len(usage_res.data) if usage_res.data else 0

    if daily_used >= daily_limit:
        return {
            "allowed": False,
            "reason": f"Has alcanzado el límite diario de {daily_limit} generaciones.",
        }

    return {"allowed": True, "daily_used": daily_used, "daily_limit": daily_limit}


def log_ai_usage(
    user_id: str,
    function_name: str,
    model: str,
    kind: str,
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
    success: bool,
    error_message: str = "",
    metadata: dict | None = None,
) -> None:
    admin = get_supabase_admin()
    admin.table("ai_usage_logs").insert({
        "user_id": user_id,
        "function_name": function_name,
        "model": model,
        "kind": kind,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost_usd": estimated_cost,
        "success": success,
        "error_message": error_message,
        "metadata": metadata or {},
    }).execute()
