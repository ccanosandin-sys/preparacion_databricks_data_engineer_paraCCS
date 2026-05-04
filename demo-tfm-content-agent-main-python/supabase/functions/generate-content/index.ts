// Edge function: generate-content
// Devuelve JSON estructurado específico para cada formato.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const SYSTEMS: Record<string, string> = {
  short:
    "Eres guionista de Shorts/Reels (vídeo vertical 9:16, 30-60s). Devuelves SIEMPRE el resultado llamando a la herramienta `short_script`. Hook brutal en 3s, 4-6 beats con duración en segundos, B-roll por beat, caption on-screen corto, CTA final, 5 hashtags.",
  carousel:
    "Eres diseñador de carruseles para Instagram/LinkedIn (slides cuadrados 1:1). Devuelves SIEMPRE llamando a `carousel_deck`. 6-8 slides: portada con hook visual, 4-6 slides de contenido (titular grande + 1-2 frases), penúltima de resumen, última de CTA. Texto MUY conciso (Instagram safe-zone).",
  post:
    "Eres copywriter de posts de feed (LinkedIn/Instagram caption). Devuelves SIEMPRE llamando a `text_post`. Hook potente en 1ª línea, cuerpo en frases cortas con saltos de línea dobles, opcionalmente lista con bullets, P.D./CTA al final, 3-6 hashtags.",
  thread:
    "Eres creador de threads de X/Twitter. Devuelves SIEMPRE llamando a `x_thread`. 6-10 tweets numerados. Tweet 1 = hook (≤220 chars, sin numerar). Tweets 2..N-1 = valor concreto (≤270 chars cada uno). Último tweet = CTA + recap. Cada tweet debe sostenerse solo.",
  insights:
    "Eres analista de tendencias para creadores. A partir de la lista de noticias dada, devuelve markdown limpio con: 1) 3 patrones detectados, 2) 3 oportunidades de contenido (con título sugerido), 3) 1 riesgo o tendencia que se enfría.",
};

const TOOLS: Record<string, unknown> = {
  short: { type: "function", function: { name: "short_script", description: "Guion estructurado para un Short/Reel vertical 9:16.", parameters: { type: "object", properties: { title: { type: "string" }, hook: { type: "object", properties: { text: { type: "string" }, caption: { type: "string" }, broll: { type: "string" } }, required: ["text", "caption", "broll"], additionalProperties: false }, beats: { type: "array", minItems: 3, maxItems: 6, items: { type: "object", properties: { seconds: { type: "number" }, voiceover: { type: "string" }, caption: { type: "string" }, broll: { type: "string" } }, required: ["seconds", "voiceover", "caption", "broll"], additionalProperties: false } }, cta: { type: "string" }, hashtags: { type: "array", items: { type: "string" }, minItems: 3, maxItems: 6 } }, required: ["title", "hook", "beats", "cta", "hashtags"], additionalProperties: false } } },
  carousel: { type: "function", function: { name: "carousel_deck", description: "Carrusel cuadrado 1:1 de 6-8 slides.", parameters: { type: "object", properties: { title: { type: "string" }, slides: { type: "array", minItems: 6, maxItems: 8, items: { type: "object", properties: { kind: { type: "string", enum: ["cover", "content", "summary", "cta"] }, headline: { type: "string" }, body: { type: "string" }, accent: { type: "string" } }, required: ["kind", "headline", "body", "accent"], additionalProperties: false } }, caption: { type: "string" }, hashtags: { type: "array", items: { type: "string" }, minItems: 3, maxItems: 8 } }, required: ["title", "slides", "caption", "hashtags"], additionalProperties: false } } },
  post: { type: "function", function: { name: "text_post", description: "Post largo de feed.", parameters: { type: "object", properties: { hook: { type: "string" }, body: { type: "string" }, bullets: { type: "array", items: { type: "string" } }, cta: { type: "string" }, hashtags: { type: "array", items: { type: "string" }, minItems: 3, maxItems: 6 } }, required: ["hook", "body", "bullets", "cta", "hashtags"], additionalProperties: false } } },
  thread: { type: "function", function: { name: "x_thread", description: "Thread de X/Twitter.", parameters: { type: "object", properties: { topic: { type: "string" }, tweets: { type: "array", minItems: 6, maxItems: 10, items: { type: "object", properties: { role: { type: "string", enum: ["hook", "body", "cta"] }, text: { type: "string" } }, required: ["role", "text"], additionalProperties: false } } }, required: ["topic", "tweets"], additionalProperties: false } } },
};

const MODEL_BY_FORMAT: Record<string, string> = {
  short: "google/gemini-2.5-flash",
  carousel: "google/gemini-2.5-flash",
  post: "google/gemini-2.5-pro",
  thread: "google/gemini-2.5-pro",
  insights: "google/gemini-2.5-pro",
};

// Tarifas estimadas (USD por 1M tokens) — aproximación
const PRICING: Record<string, { in: number; out: number }> = {
  "google/gemini-2.5-flash": { in: 0.3, out: 2.5 },
  "google/gemini-2.5-pro": { in: 1.25, out: 10 },
  "google/gemini-2.5-flash-lite": { in: 0.1, out: 0.4 },
};

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const adminClient = createClient(SUPABASE_URL, SERVICE_KEY);
  let userId: string | null = null;
  let modelUsed = "";

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY missing");

    // Auth
    const authHeader = req.headers.get("Authorization") ?? "";
    if (authHeader.startsWith("Bearer ")) {
      const userClient = createClient(SUPABASE_URL, ANON_KEY, {
        global: { headers: { Authorization: authHeader } },
      });
      const { data: u } = await userClient.auth.getUser();
      userId = u?.user?.id ?? null;
    }
    if (!userId) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Ban check
    const { data: ban } = await adminClient.from("user_bans").select("reason").eq("user_id", userId).maybeSingle();
    if (ban) {
      return new Response(JSON.stringify({ error: "Tu cuenta está bloqueada. Motivo: " + (ban.reason || "no especificado") }), {
        status: 403,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Quota check (daily content)
    const sinceDay = new Date(); sinceDay.setUTCHours(0, 0, 0, 0);
    const [{ data: quota }, { count: todayCount }] = await Promise.all([
      adminClient.from("user_quotas").select("daily_content_limit").eq("user_id", userId).maybeSingle(),
      adminClient.from("ai_usage_logs").select("*", { count: "exact", head: true }).eq("user_id", userId).eq("kind", "content").eq("success", true).gte("created_at", sinceDay.toISOString()),
    ]);
    const dailyLimit = quota?.daily_content_limit ?? 50;
    if ((todayCount ?? 0) >= dailyLimit) {
      return new Response(JSON.stringify({ error: `Límite diario alcanzado (${dailyLimit} generaciones/día). Vuelve mañana o pide más cuota a un admin.` }), {
        status: 429,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json().catch(() => ({}));
    const format: string = (body.format ?? "short").toString();
    const topic: string = (body.topic ?? "").toString().slice(0, 500);
    const tone: string = (body.tone ?? "cercano y experto").toString().slice(0, 120);
    const boost: string = (body.boost ?? "").toString().slice(0, 600);
    const context = body.context;

    const system = SYSTEMS[format] ?? SYSTEMS.post;
    const model = MODEL_BY_FORMAT[format] ?? "google/gemini-2.5-flash";
    modelUsed = model;

    let userPrompt = `Tema: ${topic}\nTono: ${tone}\nIdioma: español.`;
    if (boost) userPrompt += `\n${boost}`;
    if (context && Array.isArray(context)) {
      userPrompt += `\n\nContexto (noticias recientes):\n${context.slice(0, 20).map((c: { title?: string; topic?: string; summary?: string }, i: number) => `${i + 1}. [${c.topic ?? "-"}] ${c.title ?? ""} — ${c.summary ?? ""}`).join("\n")}`;
    }

    const payload: Record<string, unknown> = {
      model,
      messages: [{ role: "system", content: system }, { role: "user", content: userPrompt }],
    };
    const tool = TOOLS[format];
    if (tool) {
      payload.tools = [tool];
      const fnName = (tool as { function: { name: string } }).function.name;
      payload.tool_choice = { type: "function", function: { name: fnName } };
    }

    const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${LOVABLE_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const t = await res.text();
      console.error("AI error", res.status, t);
      await adminClient.from("ai_usage_logs").insert({ user_id: userId, function_name: "generate-content", model, kind: "content", success: false, error_message: `gateway_${res.status}` });
      if (res.status === 429) return new Response(JSON.stringify({ error: "Límite de uso alcanzado, intenta en un minuto." }), { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } });
      if (res.status === 402) return new Response(JSON.stringify({ error: "Sin créditos AI." }), { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } });
      throw new Error(`AI gateway ${res.status}`);
    }

    const data = await res.json();
    const usage = data?.usage ?? {};
    const tokensIn = Number(usage.prompt_tokens ?? 0);
    const tokensOut = Number(usage.completion_tokens ?? 0);
    const price = PRICING[model] ?? { in: 0.3, out: 2.5 };
    const cost = (tokensIn * price.in + tokensOut * price.out) / 1_000_000;

    await adminClient.from("ai_usage_logs").insert({
      user_id: userId, function_name: "generate-content", model, kind: "content",
      tokens_in: tokensIn, tokens_out: tokensOut, estimated_cost_usd: cost.toFixed(5), success: true,
      metadata: { format, topic: topic.slice(0, 100) },
    });

    if (tool) {
      const call = data?.choices?.[0]?.message?.tool_calls?.[0];
      const argsStr = call?.function?.arguments ?? "{}";
      let structured: unknown = null;
      try { structured = JSON.parse(argsStr); } catch { structured = null; }
      const fallback = data?.choices?.[0]?.message?.content ?? "";
      return new Response(JSON.stringify({ format, structured, content: fallback, model }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const content = data?.choices?.[0]?.message?.content ?? "";
    return new Response(JSON.stringify({ format, content, model }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("generate-content error", e);
    if (userId) {
      await adminClient.from("ai_usage_logs").insert({ user_id: userId, function_name: "generate-content", model: modelUsed, kind: "content", success: false, error_message: (e as Error).message?.slice(0, 500) }).catch(() => {});
    }
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
