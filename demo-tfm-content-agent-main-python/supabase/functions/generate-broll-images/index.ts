// Edge function: generate-broll-images
// Genera 1 imagen 9:16 por beat usando Nano Banana (gemini-2.5-flash-image),
// las sube al bucket "short-assets" y devuelve signed URLs reproducibles.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

type BrollPrompt = { id: string; prompt: string };

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY missing");

    const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    // Auth: necesitamos saber qué user es para guardar en su carpeta
    const authHeader = req.headers.get("Authorization") ?? "";
    const userClient = createClient(SUPABASE_URL, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: u } = await userClient.auth.getUser();
    if (!u?.user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const userId = u.user.id;
    const admin = createClient(SUPABASE_URL, SERVICE_KEY);

    // Ban check
    const { data: ban } = await admin.from("user_bans").select("reason").eq("user_id", userId).maybeSingle();
    if (ban) {
      return new Response(JSON.stringify({ error: "Cuenta bloqueada: " + (ban.reason || "") }), {
        status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Quota check (daily images)
    const sinceDay = new Date(); sinceDay.setUTCHours(0, 0, 0, 0);
    const [{ data: quota }, { data: usedRows }] = await Promise.all([
      admin.from("user_quotas").select("daily_image_limit").eq("user_id", userId).maybeSingle(),
      admin.from("ai_usage_logs").select("images_count").eq("user_id", userId).eq("kind", "image").eq("success", true).gte("created_at", sinceDay.toISOString()),
    ]);
    const dailyImageLimit = quota?.daily_image_limit ?? 30;
    const used = (usedRows ?? []).reduce((s, r) => s + (r.images_count ?? 0), 0);

    const body = await req.json().catch(() => ({}));
    const prompts: BrollPrompt[] = Array.isArray(body.prompts) ? body.prompts.slice(0, 8) : [];
    if (used + prompts.length > dailyImageLimit) {
      return new Response(JSON.stringify({ error: `Límite diario de imágenes alcanzado (${dailyImageLimit}/día). Llevas ${used}.` }), {
        status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const style: string = (body.style ?? "cinematic, modern, bright lighting, professional").toString().slice(0, 200);
    if (!prompts.length) {
      return new Response(JSON.stringify({ error: "No prompts" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const shortId = crypto.randomUUID();

    const results = await Promise.all(
      prompts.map(async (p) => {
        const fullPrompt = `Vertical 9:16 cinematic photo, ${style}. Scene: ${p.prompt}. No text, no watermarks, no logos. Single subject focus, shallow depth of field.`;
        const aiRes = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
          method: "POST",
          headers: { Authorization: `Bearer ${LOVABLE_API_KEY}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: "google/gemini-2.5-flash-image", messages: [{ role: "user", content: fullPrompt }], modalities: ["image", "text"] }),
        });
        if (!aiRes.ok) {
          const t = await aiRes.text();
          console.error("AI image error", aiRes.status, t.slice(0, 300));
          return { id: p.id, url: null, error: `ai_${aiRes.status}` };
        }
        const aiData = await aiRes.json();
        const dataUrl: string | undefined = aiData?.choices?.[0]?.message?.images?.[0]?.image_url?.url;
        if (!dataUrl?.startsWith("data:")) return { id: p.id, url: null, error: "no_image" };
        const [, b64] = dataUrl.split(",", 2);
        const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        const path = `${userId}/${shortId}/${p.id}.png`;
        const { error: upErr } = await admin.storage.from("short-assets").upload(path, bin, { contentType: "image/png", upsert: true });
        if (upErr) {
          console.error("upload error", upErr);
          return { id: p.id, url: null, error: "upload_failed" };
        }
        const { data: signed } = await admin.storage.from("short-assets").createSignedUrl(path, 60 * 60 * 24);
        return { id: p.id, url: signed?.signedUrl ?? null };
      }),
    );

    const successCount = results.filter((r) => r.url).length;
    const cost = successCount * 0.039; // Nano Banana ~$0.039/img
    await admin.from("ai_usage_logs").insert({
      user_id: userId, function_name: "generate-broll-images", model: "google/gemini-2.5-flash-image",
      kind: "image", images_count: successCount, estimated_cost_usd: cost.toFixed(5),
      success: successCount > 0, error_message: successCount === 0 ? "all_failed" : null,
    });

    return new Response(JSON.stringify({ shortId, images: results }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("generate-broll-images error", e);
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
