// Edge function: fetch-news
// Estrategia GRATIS: Google News RSS (titulares reales) + Lovable AI Gemini Flash
// (resumen + clasificación). Sin API keys externas.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface RssItem {
  title: string;
  link: string;
  pubDate?: string;
  source?: string;
  description?: string;
}

function decodeEntities(s: string): string {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
}

function stripHtml(s: string): string {
  return decodeEntities(s.replace(/<[^>]*>/g, "")).trim();
}

function pick(xml: string, tag: string): string | undefined {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i");
  const m = xml.match(re);
  if (!m) return undefined;
  let v = m[1].trim();
  v = v.replace(/^<!\[CDATA\[/, "").replace(/\]\]>$/, "");
  return v;
}

function parseRss(xml: string, limit = 12): RssItem[] {
  const items: RssItem[] = [];
  const re = /<item[^>]*>([\s\S]*?)<\/item>/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml)) && items.length < limit) {
    const block = m[1];
    const title = stripHtml(pick(block, "title") ?? "");
    const link = stripHtml(pick(block, "link") ?? "");
    const pubDate = pick(block, "pubDate");
    const source = stripHtml(pick(block, "source") ?? "");
    const description = stripHtml(pick(block, "description") ?? "");
    if (title && link) items.push({ title, link, pubDate, source, description });
  }
  return items;
}

async function fetchGoogleNewsRss(query: string, lang = "es"): Promise<RssItem[]> {
  const hl = lang === "es" ? "es-419" : "en-US";
  const gl = lang === "es" ? "ES" : "US";
  const ceid = lang === "es" ? "ES:es-419" : "US:en";
  const url = `https://news.google.com/rss/search?q=${encodeURIComponent(
    query,
  )}&hl=${hl}&gl=${gl}&ceid=${ceid}`;
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; LovableBot/1.0)" },
  });
  if (!res.ok) throw new Error(`Google News RSS failed: ${res.status}`);
  const xml = await res.text();
  return parseRss(xml, 15);
}

async function enrichWithAI(
  items: RssItem[],
  niche: string,
  lang: string,
): Promise<Array<{ title: string; summary: string; topic: string; source_url: string; source_name: string; published_at: string | null }>> {
  const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
  if (!LOVABLE_API_KEY) {
    // Fallback sin AI: devolvemos los RSS tal cual
    return items.map((it) => ({
      title: it.title,
      summary: it.description ?? "",
      topic: niche,
      source_url: it.link,
      source_name: it.source ?? new URL(it.link).hostname,
      published_at: it.pubDate ? new Date(it.pubDate).toISOString() : null,
    }));
  }

  const list = items
    .map((it, i) => `${i + 1}. ${it.title}${it.description ? ` — ${it.description}` : ""}`)
    .join("\n");

  const prompt = `Eres un editor de tendencias para creadores de contenido del nicho "${niche}".
Recibes titulares reales (idioma ${lang}). Para cada uno: 
- Reescribe el título en estilo claro y atractivo (max 90 chars).
- Escribe un resumen de 1-2 frases en ${lang} centrado en por qué importa al creador.
- Asigna un topic corto (1-3 palabras).
Devuelve SOLO JSON con la forma {"items":[{"index":number,"title":string,"summary":string,"topic":string}]}. No incluyas texto fuera del JSON.

Titulares:
${list}`;

  const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${LOVABLE_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "google/gemini-2.5-flash",
      messages: [
        { role: "system", content: "Devuelves siempre JSON válido." },
        { role: "user", content: prompt },
      ],
      response_format: { type: "json_object" },
    }),
  });

  if (!res.ok) {
    console.error("Lovable AI error", res.status, await res.text());
    // Fallback sin AI
    return items.map((it) => ({
      title: it.title,
      summary: it.description ?? "",
      topic: niche,
      source_url: it.link,
      source_name: it.source ?? new URL(it.link).hostname,
      published_at: it.pubDate ? new Date(it.pubDate).toISOString() : null,
    }));
  }

  const data = await res.json();
  const content = data?.choices?.[0]?.message?.content ?? "{}";
  let parsed: { items?: Array<{ index: number; title: string; summary: string; topic: string }> } = {};
  try {
    parsed = JSON.parse(content);
  } catch {
    parsed = {};
  }
  const enrichedById = new Map<number, { title: string; summary: string; topic: string }>();
  (parsed.items ?? []).forEach((x) => enrichedById.set(x.index, x));

  return items.map((it, i) => {
    const e = enrichedById.get(i + 1);
    return {
      title: e?.title || it.title,
      summary: e?.summary || it.description || "",
      topic: e?.topic || niche,
      source_url: it.link,
      source_name: it.source ?? (() => {
        try { return new URL(it.link).hostname; } catch { return "news"; }
      })(),
      published_at: it.pubDate ? new Date(it.pubDate).toISOString() : null,
    };
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const authHeader = req.headers.get("Authorization") ?? "";

    const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
      global: { headers: { Authorization: authHeader } },
    });

    const userClient = createClient(SUPABASE_URL, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData, error: userErr } = await userClient.auth.getUser();
    if (userErr || !userData?.user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const userId = userData.user.id;

    const body = await req.json().catch(() => ({}));
    const niche: string = (body.niche ?? body.topic ?? "marketing digital").toString().slice(0, 120);
    const lang: string = (body.lang ?? "es").toString().slice(0, 5);

    const rss = await fetchGoogleNewsRss(niche, lang);
    if (rss.length === 0) {
      return new Response(JSON.stringify({ items: [], message: "No results" }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const enriched = await enrichWithAI(rss.slice(0, 10), niche, lang);

    // Persistencia con dedupe por (user_id, source_url)
    const rows = enriched.map((e) => ({
      user_id: userId,
      title: e.title,
      summary: e.summary,
      topic: e.topic,
      source_url: e.source_url,
      source_name: e.source_name,
      published_at: e.published_at,
      language: lang,
      raw: e as unknown as Record<string, unknown>,
    }));

    const { data: inserted, error: insErr } = await supabase
      .from("news_items")
      .upsert(rows, { onConflict: "user_id,source_url", ignoreDuplicates: false })
      .select();

    if (insErr) {
      console.error("Insert error", insErr);
    }

    return new Response(
      JSON.stringify({ items: inserted ?? rows, count: (inserted ?? rows).length }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (e) {
    console.error("fetch-news error", e);
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
