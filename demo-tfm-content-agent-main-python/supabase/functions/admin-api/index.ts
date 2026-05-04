// Edge function: admin-api
// Acciones de administración protegidas por rol admin.
// Acepta { action: string, ...params }

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;

    const authHeader = req.headers.get("Authorization") ?? "";
    if (!authHeader.startsWith("Bearer ")) return json({ error: "Unauthorized" }, 401);

    const userClient = createClient(SUPABASE_URL, ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: u } = await userClient.auth.getUser();
    if (!u?.user) return json({ error: "Unauthorized" }, 401);

    const admin = createClient(SUPABASE_URL, SERVICE_KEY);

    // verify admin role
    const { data: roleRow } = await admin
      .from("user_roles")
      .select("role")
      .eq("user_id", u.user.id)
      .eq("role", "admin")
      .maybeSingle();
    if (!roleRow) return json({ error: "Forbidden" }, 403);

    const body = await req.json().catch(() => ({}));
    const action: string = body.action ?? "";

    // Audit helper for sensitive actions
    const AUDITED_ACTIONS = new Set([
      "set_admin", "ban_user", "unban_user", "delete_user", "set_quota",
      "delete_content", "update_settings", "upsert_plan",
      "manual_subscribe", "cancel_subscription", "manual_payment", "refund_payment",
    ]);
    const audit = async (params: { action: string; target_user_id?: string | null; payload?: unknown; result?: unknown; success?: boolean; error_message?: string | null; }) => {
      try {
        let target_email: string | null = null;
        if (params.target_user_id) {
          const { data: tu } = await admin.auth.admin.getUserById(params.target_user_id);
          target_email = tu?.user?.email ?? null;
        }
        await admin.from("admin_audit_logs").insert({
          admin_id: u.user.id,
          admin_email: u.user.email ?? null,
          target_user_id: params.target_user_id ?? null,
          target_user_email: target_email,
          action: params.action,
          payload: params.payload ?? null,
          result: params.result ?? null,
          success: params.success ?? true,
          error_message: params.error_message ?? null,
          ip_address: req.headers.get("x-forwarded-for") ?? req.headers.get("cf-connecting-ip") ?? null,
          user_agent: req.headers.get("user-agent") ?? null,
        });
      } catch (e) {
        console.error("audit log failed", e);
      }
    };

    // Resolve target user_id for audit from common body fields
    const resolveTargetUserId = async (): Promise<string | null> => {
      if (body.user_id) return body.user_id;
      if (body.subscription_id) {
        const { data } = await admin.from("subscriptions").select("user_id").eq("id", body.subscription_id).maybeSingle();
        return data?.user_id ?? null;
      }
      if (action === "refund_payment" && body.id) {
        const { data } = await admin.from("payments").select("user_id").eq("id", body.id).maybeSingle();
        return data?.user_id ?? null;
      }
      if (action === "delete_content" && body.id) {
        const { data } = await admin.from("contents").select("user_id").eq("id", body.id).maybeSingle();
        return data?.user_id ?? null;
      }
      return null;
    };

    let targetForAudit: string | null = null;
    if (AUDITED_ACTIONS.has(action)) {
      targetForAudit = await resolveTargetUserId();
    }

    const auditPayload = { ...body };
    delete (auditPayload as any).action;

    let response: Response;
    try {
      response = await handleAction();
    } catch (err) {
      if (AUDITED_ACTIONS.has(action)) {
        await audit({ action, target_user_id: targetForAudit, payload: auditPayload, success: false, error_message: (err as Error).message });
      }
      throw err;
    }

    if (AUDITED_ACTIONS.has(action)) {
      const ok = response.status >= 200 && response.status < 300;
      let resultBody: unknown = null;
      try {
        const cloned = response.clone();
        resultBody = await cloned.json();
      } catch { /* ignore */ }
      await audit({
        action,
        target_user_id: targetForAudit,
        payload: auditPayload,
        result: resultBody,
        success: ok,
        error_message: ok ? null : (resultBody && typeof resultBody === "object" ? (resultBody as any).error ?? null : null),
      });
    }
    return response;

    async function handleAction(): Promise<Response> {
    switch (action) {
      case "overview": {
        const since30 = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString();
        const since7 = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString();
        const since1 = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

        const [{ data: usersList }, contentsAgg, usageAgg, banCount] = await Promise.all([
          admin.auth.admin.listUsers({ page: 1, perPage: 1000 }),
          admin.from("contents").select("format, created_at, user_id"),
          admin.from("ai_usage_logs").select("kind, success, estimated_cost_usd, created_at, user_id, function_name"),
          admin.from("user_bans").select("user_id", { count: "exact", head: true }),
        ]);

        const users = usersList?.users ?? [];
        const totalUsers = users.length;
        const dau = new Set(users.filter((x) => x.last_sign_in_at && x.last_sign_in_at > since1).map((x) => x.id)).size;
        const wau = new Set(users.filter((x) => x.last_sign_in_at && x.last_sign_in_at > since7).map((x) => x.id)).size;
        const mau = new Set(users.filter((x) => x.last_sign_in_at && x.last_sign_in_at > since30).map((x) => x.id)).size;
        const newSignups7 = users.filter((x) => x.created_at > since7).length;

        const contents = contentsAgg.data ?? [];
        const usage = usageAgg.data ?? [];

        // signups per day (last 30)
        const days: { day: string; signups: number; contents: number; ai_calls: number; cost: number }[] = [];
        for (let i = 29; i >= 0; i--) {
          const d = new Date();
          d.setUTCHours(0, 0, 0, 0);
          d.setUTCDate(d.getUTCDate() - i);
          const key = d.toISOString().slice(0, 10);
          days.push({ day: key, signups: 0, contents: 0, ai_calls: 0, cost: 0 });
        }
        const dayIndex = new Map(days.map((d, i) => [d.day, i]));
        for (const u2 of users) {
          const k = (u2.created_at ?? "").slice(0, 10);
          const i = dayIndex.get(k);
          if (i !== undefined) days[i].signups++;
        }
        for (const c of contents) {
          const k = (c.created_at ?? "").slice(0, 10);
          const i = dayIndex.get(k);
          if (i !== undefined) days[i].contents++;
        }
        for (const r of usage) {
          const k = (r.created_at ?? "").slice(0, 10);
          const i = dayIndex.get(k);
          if (i !== undefined) {
            days[i].ai_calls++;
            days[i].cost += Number(r.estimated_cost_usd ?? 0);
          }
        }

        const formatCounts: Record<string, number> = {};
        for (const c of contents) formatCounts[c.format] = (formatCounts[c.format] ?? 0) + 1;

        const totalAiCalls = usage.length;
        const totalAiErrors = usage.filter((r) => !r.success).length;
        const totalCost = usage.reduce((s, r) => s + Number(r.estimated_cost_usd ?? 0), 0);

        // Top consumers (last 30d)
        const consumerMap = new Map<string, { calls: number; cost: number }>();
        for (const r of usage) {
          if (r.created_at < since30) continue;
          const cur = consumerMap.get(r.user_id) ?? { calls: 0, cost: 0 };
          cur.calls++;
          cur.cost += Number(r.estimated_cost_usd ?? 0);
          consumerMap.set(r.user_id, cur);
        }
        const userMap = new Map(users.map((x) => [x.id, x.email ?? "(sin email)"]));
        const topConsumers = [...consumerMap.entries()]
          .map(([user_id, v]) => ({ user_id, email: userMap.get(user_id) ?? "(eliminado)", ...v }))
          .sort((a, b) => b.calls - a.calls)
          .slice(0, 10);

        return json({
          stats: {
            totalUsers,
            dau,
            wau,
            mau,
            newSignups7,
            totalContents: contents.length,
            totalAiCalls,
            totalAiErrors,
            totalCost: Number(totalCost.toFixed(4)),
            bannedCount: banCount.count ?? 0,
          },
          days,
          formatCounts,
          topConsumers,
        });
      }

      case "list_users": {
        const search: string = (body.search ?? "").toLowerCase();
        const { data: usersList } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 });
        const users = usersList?.users ?? [];
        const [{ data: roles }, { data: bans }, { data: contentsCounts }, { data: usageCounts }] = await Promise.all([
          admin.from("user_roles").select("user_id, role"),
          admin.from("user_bans").select("user_id, reason, created_at"),
          admin.from("contents").select("user_id"),
          admin.from("ai_usage_logs").select("user_id, estimated_cost_usd"),
        ]);
        const roleByUser = new Map<string, string[]>();
        for (const r of roles ?? []) {
          const arr = roleByUser.get(r.user_id) ?? [];
          arr.push(r.role);
          roleByUser.set(r.user_id, arr);
        }
        const banByUser = new Map((bans ?? []).map((b) => [b.user_id, b]));
        const contentByUser = new Map<string, number>();
        for (const c of contentsCounts ?? []) {
          contentByUser.set(c.user_id, (contentByUser.get(c.user_id) ?? 0) + 1);
        }
        const usageByUser = new Map<string, { calls: number; cost: number }>();
        for (const u2 of usageCounts ?? []) {
          const cur = usageByUser.get(u2.user_id) ?? { calls: 0, cost: 0 };
          cur.calls++;
          cur.cost += Number(u2.estimated_cost_usd ?? 0);
          usageByUser.set(u2.user_id, cur);
        }
        const enriched = users
          .map((x) => ({
            id: x.id,
            email: x.email,
            created_at: x.created_at,
            last_sign_in_at: x.last_sign_in_at,
            email_confirmed_at: x.email_confirmed_at,
            roles: roleByUser.get(x.id) ?? [],
            banned: !!banByUser.get(x.id),
            ban_reason: banByUser.get(x.id)?.reason ?? null,
            contents: contentByUser.get(x.id) ?? 0,
            ai_calls: usageByUser.get(x.id)?.calls ?? 0,
            ai_cost: Number((usageByUser.get(x.id)?.cost ?? 0).toFixed(4)),
          }))
          .filter((x) => !search || (x.email ?? "").toLowerCase().includes(search))
          .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
        return json({ users: enriched });
      }

      case "set_admin": {
        const target: string = body.user_id;
        const make: boolean = !!body.make;
        if (!target) return json({ error: "user_id required" }, 400);
        if (make) {
          await admin.from("user_roles").upsert({ user_id: target, role: "admin" }, { onConflict: "user_id,role" });
        } else {
          await admin.from("user_roles").delete().eq("user_id", target).eq("role", "admin");
        }
        return json({ ok: true });
      }

      case "ban_user": {
        const target: string = body.user_id;
        const reason: string = body.reason ?? "";
        if (!target) return json({ error: "user_id required" }, 400);
        await admin.from("user_bans").upsert({ user_id: target, reason, banned_by: u.user.id });
        return json({ ok: true });
      }

      case "unban_user": {
        const target: string = body.user_id;
        if (!target) return json({ error: "user_id required" }, 400);
        await admin.from("user_bans").delete().eq("user_id", target);
        return json({ ok: true });
      }

      case "delete_user": {
        const target: string = body.user_id;
        if (!target) return json({ error: "user_id required" }, 400);
        if (target === u.user.id) return json({ error: "No te puedes eliminar a ti mismo" }, 400);
        const { error } = await admin.auth.admin.deleteUser(target);
        if (error) return json({ error: error.message }, 400);
        return json({ ok: true });
      }

      case "set_quota": {
        const target: string = body.user_id;
        const q = body.quota ?? {};
        if (!target) return json({ error: "user_id required" }, 400);
        await admin.from("user_quotas").upsert({
          user_id: target,
          daily_content_limit: q.daily_content_limit ?? 50,
          daily_image_limit: q.daily_image_limit ?? 30,
          monthly_content_limit: q.monthly_content_limit ?? 1000,
          monthly_image_limit: q.monthly_image_limit ?? 500,
        });
        return json({ ok: true });
      }

      case "get_quota": {
        const target: string = body.user_id;
        const { data } = await admin.from("user_quotas").select("*").eq("user_id", target).maybeSingle();
        return json({ quota: data });
      }

      case "list_recent_contents": {
        const { data } = await admin
          .from("contents")
          .select("id, user_id, title, format, status, created_at, topic")
          .order("created_at", { ascending: false })
          .limit(50);
        const userIds = [...new Set((data ?? []).map((c) => c.user_id))];
        const { data: usersList } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 });
        const userMap = new Map((usersList?.users ?? []).map((u2) => [u2.id, u2.email]));
        const enriched = (data ?? []).map((c) => ({ ...c, email: userMap.get(c.user_id) ?? "(eliminado)" }));
        return json({ contents: enriched });
      }

      case "delete_content": {
        const id: string = body.id;
        if (!id) return json({ error: "id required" }, 400);
        await admin.from("contents").delete().eq("id", id);
        return json({ ok: true });
      }

      case "list_recent_errors": {
        const { data } = await admin
          .from("ai_usage_logs")
          .select("*")
          .eq("success", false)
          .order("created_at", { ascending: false })
          .limit(50);
        return json({ errors: data ?? [] });
      }

      case "update_settings": {
        const updates: Record<string, unknown> = body.settings ?? {};
        for (const [k, v] of Object.entries(updates)) {
          await admin.from("app_settings").upsert({ key: k, value: v, updated_by: u.user.id, updated_at: new Date().toISOString() });
        }
        return json({ ok: true });
      }

      case "get_settings": {
        const { data } = await admin.from("app_settings").select("*");
        return json({ settings: data ?? [] });
      }

      case "finance_overview": {
        const now = new Date();
        const sinceYear = new Date(now); sinceYear.setUTCMonth(sinceYear.getUTCMonth() - 11); sinceYear.setUTCDate(1); sinceYear.setUTCHours(0,0,0,0);
        const monthStart = new Date(now); monthStart.setUTCDate(1); monthStart.setUTCHours(0,0,0,0);
        const prevMonthStart = new Date(monthStart); prevMonthStart.setUTCMonth(prevMonthStart.getUTCMonth() - 1);

        const [{ data: subs }, { data: plans }, { data: payments }, { data: usage }, { data: usersList }] = await Promise.all([
          admin.from("subscriptions").select("*"),
          admin.from("plans").select("*"),
          admin.from("payments").select("*").gte("created_at", sinceYear.toISOString()),
          admin.from("ai_usage_logs").select("created_at, estimated_cost_usd, user_id").gte("created_at", sinceYear.toISOString()),
          admin.auth.admin.listUsers({ page: 1, perPage: 1000 }),
        ]);

        const planById = new Map((plans ?? []).map((p) => [p.id, p]));
        const monthlyCents = (s: any) => {
          const p = planById.get(s.plan_id); if (!p) return 0;
          const v = s.interval === "yearly" ? Math.round((p.price_yearly_cents ?? 0) / 12) : (p.price_monthly_cents ?? 0);
          return v;
        };

        const activeSubs = (subs ?? []).filter((s) => s.status === "active" || s.status === "trialing");
        const mrrCents = activeSubs.reduce((s, x) => s + monthlyCents(x), 0);
        const arrCents = mrrCents * 12;
        const arpuCents = activeSubs.length ? Math.round(mrrCents / activeSubs.length) : 0;

        // monthly buckets last 12
        const months: { month: string; mrr_cents: number; revenue_cents: number; new_subs: number; churned_subs: number; ai_cost_cents: number }[] = [];
        for (let i = 11; i >= 0; i--) {
          const d = new Date(now); d.setUTCMonth(d.getUTCMonth() - i); d.setUTCDate(1); d.setUTCHours(0,0,0,0);
          months.push({ month: d.toISOString().slice(0, 7), mrr_cents: 0, revenue_cents: 0, new_subs: 0, churned_subs: 0, ai_cost_cents: 0 });
        }
        const mIdx = new Map(months.map((m, i) => [m.month, i]));

        for (const p of payments ?? []) {
          if (p.status !== "succeeded") continue;
          const k = (p.created_at ?? "").slice(0, 7);
          const i = mIdx.get(k); if (i !== undefined) months[i].revenue_cents += p.amount_cents ?? 0;
        }
        for (const s of subs ?? []) {
          const created = (s.created_at ?? "").slice(0, 7);
          const i = mIdx.get(created); if (i !== undefined) months[i].new_subs++;
          if (s.canceled_at) {
            const k = s.canceled_at.slice(0, 7);
            const j = mIdx.get(k); if (j !== undefined) months[j].churned_subs++;
          }
        }
        // MRR snapshot per month: sum monthly value of subs that were active at month end
        for (let i = 0; i < months.length; i++) {
          const monthEnd = new Date(months[i].month + "-01T00:00:00Z");
          monthEnd.setUTCMonth(monthEnd.getUTCMonth() + 1);
          const activeAt = (subs ?? []).filter((s) => {
            const start = new Date(s.created_at);
            const end = s.canceled_at ? new Date(s.canceled_at) : null;
            return start < monthEnd && (!end || end >= monthEnd);
          });
          months[i].mrr_cents = activeAt.reduce((acc, x) => acc + monthlyCents(x), 0);
        }
        for (const r of usage ?? []) {
          const k = (r.created_at ?? "").slice(0, 7);
          const i = mIdx.get(k); if (i !== undefined) months[i].ai_cost_cents += Math.round(Number(r.estimated_cost_usd ?? 0) * 100);
        }

        const thisMonth = months[months.length - 1];
        const lastMonth = months[months.length - 2];
        const mrrGrowth = lastMonth?.mrr_cents ? ((thisMonth.mrr_cents - lastMonth.mrr_cents) / lastMonth.mrr_cents) * 100 : 0;

        // Churn rate this month: churned / active at start of month
        const churnRate = (lastMonth && (lastMonth.mrr_cents > 0))
          ? ((thisMonth.churned_subs / Math.max(1, activeSubs.length + thisMonth.churned_subs)) * 100)
          : 0;

        // LTV ≈ ARPU / churn (mensual, con churn mínimo 1% para evitar infinito)
        const ltvCents = Math.round(arpuCents / Math.max(0.01, churnRate / 100));

        // Free → Paid conversion
        const totalUsers = (usersList?.users ?? []).length;
        const paidUsers = new Set(activeSubs.filter((s) => {
          const p = planById.get(s.plan_id); return (p?.price_monthly_cents ?? 0) > 0;
        }).map((s) => s.user_id)).size;
        const conversionRate = totalUsers ? (paidUsers / totalUsers) * 100 : 0;

        // Plan breakdown
        const planBreakdown = (plans ?? []).map((p) => {
          const subsOnPlan = activeSubs.filter((s) => s.plan_id === p.id);
          return {
            key: p.key,
            name: p.name,
            active: subsOnPlan.length,
            mrr_cents: subsOnPlan.reduce((acc, s) => acc + monthlyCents(s), 0),
          };
        });

        // Top customers (by revenue last 12m)
        const revByUser = new Map<string, number>();
        for (const p of payments ?? []) {
          if (p.status !== "succeeded") continue;
          revByUser.set(p.user_id, (revByUser.get(p.user_id) ?? 0) + (p.amount_cents ?? 0));
        }
        const userMap = new Map((usersList?.users ?? []).map((x) => [x.id, x.email]));
        const topCustomers = [...revByUser.entries()]
          .map(([uid, cents]) => ({ user_id: uid, email: userMap.get(uid) ?? "(eliminado)", revenue_cents: cents }))
          .sort((a, b) => b.revenue_cents - a.revenue_cents)
          .slice(0, 10);

        // Margin: revenue this month - ai cost this month
        const aiCostThisMonth = thisMonth.ai_cost_cents;
        const grossMarginCents = thisMonth.revenue_cents - aiCostThisMonth;
        const grossMarginPct = thisMonth.revenue_cents ? (grossMarginCents / thisMonth.revenue_cents) * 100 : 0;

        // Forecast next 3/6/12 months: linear projection from MRR + growth
        const growth = mrrGrowth / 100;
        const forecast = [3, 6, 12].map((n) => ({
          months: n,
          mrr_cents: Math.round(mrrCents * Math.pow(1 + growth, n)),
          revenue_total_cents: Math.round(
            Array.from({ length: n }).reduce((acc: number, _, i) => acc + mrrCents * Math.pow(1 + growth, i + 1), 0),
          ),
        }));

        return json({
          stats: {
            mrr_cents: mrrCents,
            arr_cents: arrCents,
            arpu_cents: arpuCents,
            ltv_cents: ltvCents,
            active_subs: activeSubs.length,
            paid_users: paidUsers,
            total_users: totalUsers,
            conversion_rate: Number(conversionRate.toFixed(2)),
            churn_rate: Number(churnRate.toFixed(2)),
            mrr_growth_pct: Number(mrrGrowth.toFixed(2)),
            revenue_this_month_cents: thisMonth.revenue_cents,
            revenue_last_month_cents: lastMonth?.revenue_cents ?? 0,
            ai_cost_this_month_cents: aiCostThisMonth,
            gross_margin_cents: grossMarginCents,
            gross_margin_pct: Number(grossMarginPct.toFixed(2)),
          },
          months,
          planBreakdown,
          topCustomers,
          forecast,
        });
      }

      case "list_subscriptions": {
        const { data: subs } = await admin.from("subscriptions").select("*, plans(name, key, price_monthly_cents, price_yearly_cents, currency)").order("created_at", { ascending: false }).limit(200);
        const { data: usersList } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 });
        const userMap = new Map((usersList?.users ?? []).map((x) => [x.id, x.email]));
        return json({ subscriptions: (subs ?? []).map((s) => ({ ...s, email: userMap.get(s.user_id) ?? "(eliminado)" })) });
      }

      case "list_payments": {
        const { data } = await admin.from("payments").select("*").order("created_at", { ascending: false }).limit(200);
        const { data: usersList } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 });
        const userMap = new Map((usersList?.users ?? []).map((x) => [x.id, x.email]));
        return json({ payments: (data ?? []).map((p) => ({ ...p, email: userMap.get(p.user_id) ?? "(eliminado)" })) });
      }

      case "list_plans": {
        const { data } = await admin.from("plans").select("*").order("sort_order");
        return json({ plans: data ?? [] });
      }

      case "upsert_plan": {
        const p = body.plan ?? {};
        if (!p.key || !p.name) return json({ error: "key and name required" }, 400);
        await admin.from("plans").upsert(p, { onConflict: "key" });
        return json({ ok: true });
      }

      case "manual_subscribe": {
        const target: string = body.user_id;
        const planKey: string = body.plan_key;
        const interval: string = body.interval ?? "monthly";
        if (!target || !planKey) return json({ error: "user_id and plan_key required" }, 400);
        const { data: plan } = await admin.from("plans").select("*").eq("key", planKey).maybeSingle();
        if (!plan) return json({ error: "plan not found" }, 404);

        // cancel previous active sub
        await admin.from("subscriptions").update({ status: "canceled", canceled_at: new Date().toISOString() })
          .eq("user_id", target).in("status", ["active", "trialing"]);

        const periodEnd = new Date();
        if (interval === "yearly") periodEnd.setUTCFullYear(periodEnd.getUTCFullYear() + 1);
        else periodEnd.setUTCMonth(periodEnd.getUTCMonth() + 1);

        const { data: sub } = await admin.from("subscriptions").insert({
          user_id: target, plan_id: plan.id, interval, status: "active",
          current_period_end: periodEnd.toISOString(),
        }).select().single();

        const amount = interval === "yearly" ? plan.price_yearly_cents : plan.price_monthly_cents;
        if (amount > 0 && sub) {
          await admin.from("payments").insert({
            user_id: target, subscription_id: sub.id, amount_cents: amount, currency: plan.currency,
            status: "succeeded", reason: "subscription", description: `${plan.name} (${interval})`,
          });
        }
        return json({ ok: true });
      }

      case "cancel_subscription": {
        const subId: string = body.subscription_id;
        if (!subId) return json({ error: "subscription_id required" }, 400);
        await admin.from("subscriptions").update({ status: "canceled", canceled_at: new Date().toISOString() }).eq("id", subId);
        return json({ ok: true });
      }

      case "manual_payment": {
        const target: string = body.user_id;
        const amount_cents: number = Number(body.amount_cents ?? 0);
        const currency: string = body.currency ?? "EUR";
        const reason: string = body.reason ?? "manual";
        const description: string = body.description ?? "";
        if (!target || !amount_cents) return json({ error: "user_id and amount_cents required" }, 400);
        await admin.from("payments").insert({ user_id: target, amount_cents, currency, status: "succeeded", reason, description });
        return json({ ok: true });
      }

      case "refund_payment": {
        const id: string = body.id;
        if (!id) return json({ error: "id required" }, 400);
        await admin.from("payments").update({ status: "refunded" }).eq("id", id);
        return json({ ok: true });
      }

      case "list_audit_logs": {
        const limit = Math.min(Number(body.limit ?? 200), 1000);
        const filterAction: string | null = body.filter_action ?? null;
        const filterAdmin: string | null = body.filter_admin ?? null;
        const filterTarget: string | null = body.filter_target ?? null;
        const since: string | null = body.since ?? null;
        const until: string | null = body.until ?? null;
        let q = admin.from("admin_audit_logs").select("*").order("created_at", { ascending: false }).limit(limit);
        if (filterAction) q = q.eq("action", filterAction);
        if (filterAdmin) q = q.eq("admin_id", filterAdmin);
        if (filterTarget) q = q.eq("target_user_id", filterTarget);
        if (since) q = q.gte("created_at", since);
        if (until) q = q.lte("created_at", until);
        const { data, error } = await q;
        if (error) return json({ error: error.message }, 400);
        return json({ logs: data ?? [] });
      }

      default:
        return json({ error: "unknown action" }, 400);
    }
    }
  } catch (e) {
    console.error("admin-api error", e);
    return json({ error: (e as Error).message }, 500);
  }
});
