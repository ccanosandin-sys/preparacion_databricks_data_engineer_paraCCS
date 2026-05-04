// Edge function: rank-news
// Devuelve las noticias del usuario ordenadas por afinidad
// con su perfil (topics que ha guardado/usado más) y prepara un
// "boost prompt" listo para inyectar en generate-content.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
    const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
    const auth = req.headers.get("Authorization") ?? "";
    const supabase = createClient(SUPABASE_URL, ANON, {
      global: { headers: { Authorization: auth } },
    });

    const { data: u, error: uerr } = await supabase.auth.getUser();
    if (uerr || !u.user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const uid = u.user.id;

    const [{ data: scores }, { data: news }] = await Promise.all([
      supabase.from("user_topic_scores").select("topic,score,interactions").eq("user_id", uid),
      supabase
        .from("news_items")
        .select("id,title,summary,source_url,source_name,topic,published_at,language")
        .eq("user_id", uid)
        .order("published_at", { ascending: false })
        .limit(50),
    ]);

    const scoreMap = new Map<string, number>();
    (scores ?? []).forEach((s) => scoreMap.set(s.topic, s.score));

    const now = Date.now();
    const ranked = (news ?? [])
      .map((n) => {
        const topicScore = scoreMap.get(n.topic ?? "otros") ?? 0;
        const ageHours = n.published_at
          ? (now - new Date(n.published_at).getTime()) / 36e5
          : 72;
        const recency = Math.max(0, 5 - Math.log1p(ageHours)); // ~5 al inicio, baja con el tiempo
        const total = topicScore * 1.5 + recency;
        return { ...n, score: Number(total.toFixed(2)), topic_score: topicScore };
      })
      .sort((a, b) => b.score - a.score);

    // Top topics personalizados
    const topTopics = [...(scores ?? [])]
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map((s) => s.topic);

    const boostPrompt =
      topTopics.length > 0
        ? `Preferencias del usuario detectadas: prioriza ángulos relacionados con ${topTopics.join(", ")}. Evita ángulos genéricos.`
        : "Sin histórico aún: usa ángulo genérico de alto valor.";

    return new Response(
      JSON.stringify({
        items: ranked,
        topTopics,
        boostPrompt,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (e) {
    console.error("rank-news", e);
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
