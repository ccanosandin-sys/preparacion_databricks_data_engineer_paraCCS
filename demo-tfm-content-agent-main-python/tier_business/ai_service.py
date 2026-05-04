import asyncio
import json
import httpx
from typing import Any
from tier_business.config import settings

LOVABLE_BASE_URL = "https://ai.gateway.lovable.dev/v1"

MODELS = {
    "fast": "google/gemini-2.5-flash",
    "pro": "google/gemini-2.5-pro",
}

COST_PER_1M = {
    "google/gemini-2.5-flash": {"in": 0.30, "out": 2.50},
    "google/gemini-2.5-pro": {"in": 1.25, "out": 10.00},
}

SHORT_TOOL = {
    "type": "function",
    "function": {
        "name": "short_script",
        "description": "Generate a structured short video script",
        "parameters": {
            "type": "object",
            "required": ["hook", "beats", "cta", "hashtags"],
            "properties": {
                "hook": {
                    "type": "object",
                    "required": ["text", "caption", "broll"],
                    "properties": {
                        "text": {"type": "string"},
                        "caption": {"type": "string"},
                        "broll": {"type": "string"},
                    },
                },
                "beats": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "required": ["text", "caption", "broll", "duration"],
                        "properties": {
                            "text": {"type": "string"},
                            "caption": {"type": "string"},
                            "broll": {"type": "string"},
                            "duration": {"type": "number"},
                        },
                    },
                },
                "cta": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

CAROUSEL_TOOL = {
    "type": "function",
    "function": {
        "name": "carousel_deck",
        "description": "Generate carousel slides for social media",
        "parameters": {
            "type": "object",
            "required": ["slides", "caption", "hashtags"],
            "properties": {
                "slides": {
                    "type": "array",
                    "minItems": 6,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "required": ["type", "headline", "body"],
                        "properties": {
                            "type": {"type": "string", "enum": ["cover", "content", "summary", "cta"]},
                            "headline": {"type": "string"},
                            "body": {"type": "string"},
                        },
                    },
                },
                "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

POST_TOOL = {
    "type": "function",
    "function": {
        "name": "text_post",
        "description": "Generate a text post for LinkedIn or Instagram",
        "parameters": {
            "type": "object",
            "required": ["hook", "body", "bullets", "cta", "hashtags"],
            "properties": {
                "hook": {"type": "string"},
                "body": {"type": "string"},
                "bullets": {"type": "array", "items": {"type": "string"}},
                "cta": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

THREAD_TOOL = {
    "type": "function",
    "function": {
        "name": "x_thread",
        "description": "Generate a Twitter/X thread",
        "parameters": {
            "type": "object",
            "required": ["topic", "tweets"],
            "properties": {
                "topic": {"type": "string"},
                "tweets": {
                    "type": "array",
                    "minItems": 6,
                    "maxItems": 10,
                    "items": {"type": "string"},
                },
            },
        },
    },
}

INSIGHTS_TOOL = {
    "type": "function",
    "function": {
        "name": "content_insights",
        "description": "Generate content strategy insights",
        "parameters": {
            "type": "object",
            "required": ["patterns", "opportunities", "risk"],
            "properties": {
                "patterns": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {"type": "string"},
                },
                "opportunities": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": ["title", "description"],
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "risk": {"type": "string"},
            },
        },
    },
}

FORMAT_CONFIG = {
    "short": {"tool": SHORT_TOOL, "model": MODELS["fast"]},
    "carousel": {"tool": CAROUSEL_TOOL, "model": MODELS["fast"]},
    "post": {"tool": POST_TOOL, "model": MODELS["pro"]},
    "thread": {"tool": THREAD_TOOL, "model": MODELS["pro"]},
    "insights": {"tool": INSIGHTS_TOOL, "model": MODELS["pro"]},
}

SYSTEM_PROMPTS = {
    "short": (
        "Eres un experto en contenido viral para redes sociales. "
        "Crea guiones de Shorts/Reels con gancho poderoso, estructura narrativa clara y CTA efectivo. "
        "Cada beat debe tener duración en segundos (total ~60s). El lenguaje debe ser natural y coloquial."
    ),
    "carousel": (
        "Eres un experto en carruseles virales para LinkedIn e Instagram. "
        "Crea carruseles de 6-8 slides educativos y atractivos. "
        "La portada debe generar curiosidad. El último slide siempre es CTA."
    ),
    "post": (
        "Eres un experto en copywriting para redes sociales. "
        "Crea posts con un hook que detenga el scroll, cuerpo con valor real y CTA claro. "
        "Máximo 1300 caracteres para Instagram, ilimitado para LinkedIn."
    ),
    "thread": (
        "Eres un experto en threads virales para X (Twitter). "
        "Crea threads de 6-10 tweets donde cada tweet aporta valor independientemente. "
        "El primer tweet es el hook. El último es el CTA/resumen."
    ),
    "insights": (
        "Eres un estratega de contenido. Analiza las tendencias del usuario "
        "e identifica patrones, oportunidades concretas y riesgos. Sé específico y accionable."
    ),
}


async def call_ai(
    format: str,
    topic: str,
    tone: str = "profesional",
    boost: str = "",
    context: str = "",
) -> dict[str, Any]:
    config = FORMAT_CONFIG.get(format)
    if not config:
        raise ValueError(f"Formato desconocido: {format}")

    tool = config["tool"]
    model = config["model"]
    system_prompt = SYSTEM_PROMPTS.get(format, "")

    user_prompt = f"Tema: {topic}\nTono: {tone}"
    if boost:
        user_prompt += f"\n\nPersonalización: {boost}"
    if context:
        user_prompt += f"\n\nContexto de tendencias:\n{context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if settings.LOVABLE_API_KEY:
        result = await _call_lovable(messages, tool, model)
    elif settings.GEMINI_API_KEY:
        result = await _call_gemini_direct(messages, tool, format, model)
    else:
        raise RuntimeError("Configura LOVABLE_API_KEY o GEMINI_API_KEY en .env")

    tokens_in = result.get("usage", {}).get("prompt_tokens", 0)
    tokens_out = result.get("usage", {}).get("completion_tokens", 0)
    cost_rates = COST_PER_1M.get(model, {"in": 0, "out": 0})
    estimated_cost = (tokens_in / 1_000_000 * cost_rates["in"]) + (tokens_out / 1_000_000 * cost_rates["out"])

    return {
        "format": format,
        "structured": result.get("structured"),
        "content": result.get("content", ""),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost": estimated_cost,
    }


def call_ai_sync(
    format: str,
    topic: str,
    tone: str = "profesional",
    boost: str = "",
    context: str = "",
) -> dict[str, Any]:
    return asyncio.run(call_ai(format, topic, tone, boost, context))


async def _call_lovable(messages: list, tool: dict, model: str) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.LOVABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": tool["function"]["name"]}},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{LOVABLE_BASE_URL}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    structured = None
    content_text = ""
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        args = tool_calls[0].get("function", {}).get("arguments", "{}")
        try:
            structured = json.loads(args)
        except json.JSONDecodeError:
            content_text = args
    else:
        content_text = message.get("content", "")

    return {"structured": structured, "content": content_text, "usage": data.get("usage", {})}


async def _call_gemini_direct(messages: list, tool: dict, format: str, model: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)

    model_name = model.replace("google/", "")
    gemini_model = genai.GenerativeModel(model_name)

    system_content = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
    prompt = f"{system_content}\n\n{user_content}" if system_content else user_content

    func_params = tool["function"]["parameters"]
    func_decl = genai.protos.FunctionDeclaration(
        name=tool["function"]["name"],
        description=tool["function"]["description"],
        parameters=_convert_schema(func_params),
    )
    tools_gemini = genai.protos.Tool(function_declarations=[func_decl])

    response = gemini_model.generate_content(
        prompt,
        tools=[tools_gemini],
        tool_config=genai.protos.ToolConfig(
            function_calling_config=genai.protos.FunctionCallingConfig(
                mode=genai.protos.FunctionCallingConfig.Mode.ANY
            )
        ),
    )

    structured = None
    content_text = ""
    for part in response.parts:
        if part.function_call:
            args = dict(part.function_call.args)
            structured = _proto_to_dict(args)
            break
    if not structured:
        content_text = response.text if hasattr(response, "text") else ""

    usage = {}
    if hasattr(response, "usage_metadata"):
        usage = {
            "prompt_tokens": response.usage_metadata.prompt_token_count,
            "completion_tokens": response.usage_metadata.candidates_token_count,
        }

    return {"structured": structured, "content": content_text, "usage": usage}


def _convert_schema(schema: dict) -> "genai.protos.Schema":
    import google.generativeai as genai
    type_map = {
        "object": genai.protos.Type.OBJECT,
        "array": genai.protos.Type.ARRAY,
        "string": genai.protos.Type.STRING,
        "number": genai.protos.Type.NUMBER,
        "boolean": genai.protos.Type.BOOLEAN,
        "integer": genai.protos.Type.INTEGER,
    }
    t = schema.get("type", "string")
    proto_type = type_map.get(t, genai.protos.Type.STRING)
    kwargs = {"type_": proto_type}
    if schema.get("description"):
        kwargs["description"] = schema["description"]
    if schema.get("enum"):
        kwargs["enum"] = schema["enum"]
    if t == "object" and schema.get("properties"):
        kwargs["properties"] = {k: _convert_schema(v) for k, v in schema["properties"].items()}
        if schema.get("required"):
            kwargs["required"] = schema["required"]
    if t == "array" and schema.get("items"):
        kwargs["items"] = _convert_schema(schema["items"])
    return genai.protos.Schema(**kwargs)


def _proto_to_dict(obj: Any) -> Any:
    if hasattr(obj, "items"):
        return {k: _proto_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_proto_to_dict(i) for i in obj]
    return obj


async def enrich_news_with_ai(items: list[dict]) -> list[dict]:
    if not items:
        return items
    if not (settings.LOVABLE_API_KEY or settings.GEMINI_API_KEY):
        return items

    titles = "\n".join([f"{i+1}. {item['title']}" for i, item in enumerate(items)])
    prompt = (
        "Tienes estos titulares de noticias:\n"
        f"{titles}\n\n"
        "Para cada uno devuelve un JSON array con objetos que tengan: "
        '{"index": 1, "title": "titulo mejorado", "summary": "resumen 1 frase", "topic": "categoria"}\n'
        'Topics válidos: tecnologia, marketing, negocios, ia, startups, finanzas, salud, educacion, entretenimiento, otro.\n'
        "Responde SOLO con el JSON array, sin explicaciones."
    )

    try:
        if settings.LOVABLE_API_KEY:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{LOVABLE_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LOVABLE_API_KEY}"},
                    json={
                        "model": MODELS["fast"],
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    },
                )
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
        else:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            text = response.text

        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        enriched = json.loads(text)
        if isinstance(enriched, dict):
            enriched = enriched.get("items", enriched.get("results", list(enriched.values())[0] if enriched else []))

        for e in enriched:
            idx = e.get("index", 0) - 1
            if 0 <= idx < len(items):
                items[idx]["title"] = e.get("title", items[idx]["title"])
                items[idx]["summary"] = e.get("summary", "")
                items[idx]["topic"] = e.get("topic", "otro")
    except Exception:
        pass

    return items


def enrich_news_with_ai_sync(items: list[dict]) -> list[dict]:
    return asyncio.run(enrich_news_with_ai(items))
