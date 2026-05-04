
# ContentAgent — SaaS de creación de contenido con IA que aprende de cada usuario

Plataforma multi-tenant donde creadores y empresas configuran su marca una vez, y un agente IA genera borradores de **Shorts**, **carruseles** y **posts de texto** alineados con su estilo. El usuario revisa, publica desde la propia interfaz, y el sistema **aprende qué funciona** para optimizar automáticamente las siguientes generaciones.

**Primera red integrada en el MVP: YouTube** (Shorts y vídeo). Reaprovecha el OAuth de Google del login, API muy madura, métricas excelentes vía YouTube Analytics. TikTok, Instagram y LinkedIn quedan para iteraciones siguientes.

---

## Experiencia de usuario

### 1. Onboarding (primera vez)
- Registro con email o Google.
- Se crea automáticamente un **Espacio de marca** (workspace) y el usuario entra como Owner.
- Asistente guiado en 4 pasos para definir el perfil de marca:
  1. **Identidad**: nombre, sector/nicho, propuesta de valor, audiencia objetivo.
  2. **Estilo**: tono (cercano, técnico, irónico…), do's & don'ts, palabras prohibidas, idiomas.
  3. **Branding visual**: paleta de colores, tipografías de referencia, logo.
  4. **Referencias**: 3-5 ejemplos de vídeos/posts propios o de inspiración que "quiero sonar así".

### 2. Espacios de equipo
- Un usuario puede pertenecer a varias marcas.
- Roles: **Owner**, **Editor** (crea y publica), **Viewer** (solo lee).
- Selector de marca arriba a la izquierda (estilo Notion/Linear).
- Invitaciones por email.

### 3. Generación de contenido
Pantalla "Nuevo contenido" con:
- Tipo: **Short**, **Carrusel**, **Post de texto**.
- Red destino (YouTube en MVP; resto visibles pero "próximamente").
- Tema o brief libre (1 frase basta) + opcional: tono, duración, objetivo (engagement, captación, educar…).
- Botón **Generar borrador**.

El agente devuelve, según tipo:
- **Short**: hook, guion escena por escena con timing, sugerencia visual por escena, CTA, **título optimizado para YouTube**, descripción y tags/hashtags, sugerencia de miniatura.
- **Carrusel**: portada + 5-10 slides con copy y sugerencia visual por slide, caption y hashtags.
- **Post**: 3 variantes A/B/C con longitudes distintas.

### 4. Revisión y edición
- Editor lateral con preview a la derecha (vertical 9:16 para shorts, cuadrado para carrusel).
- Edición libre del texto, regeneración de slides/escenas individuales, "hazlo más corto", "más provocador", etc.
- Estados: **Borrador → Aprobado → Programado → Publicado**.
- Feedback rápido del usuario en cada borrador: 👍 / 👎 + comentario opcional ("muy genérico", "perfecto", "cambia el hook"). Esto alimenta el aprendizaje aunque no se llegue a publicar.

### 5. Publicación y métricas (YouTube)
- Conexión OAuth con la cuenta de YouTube del usuario (canal específico si tiene varios).
- Subida del archivo de vídeo final + título + descripción + tags + miniatura desde la propia interfaz.
- Publicar ahora o programar fecha/hora.
- Pestaña **Analytics**: lista de publicaciones con visitas, likes, comentarios, shares, watch time, retención media, CTR de miniatura. Tarjetas de "tus mejores Shorts del mes".

### 6. Aprendizaje automático por usuario
Cada marca tiene un **perfil de aprendizaje** que se actualiza solo:
- Cuando un Short supera el rendimiento medio del usuario (visitas, retención, CTR), se marca como **ganador**.
- Cuando recibe 👎 o se descarta, se marca como **señal negativa**.
- Un proceso periódico (cada noche) analiza los ganadores y extrae **reglas explícitas**: "los hooks con pregunta funcionan +40%", "duración óptima 22-28s", "miniaturas con cara rinden +60% CTR", "los carruseles de 7 slides rinden mejor que los de 10".
- Estas reglas + 3-5 ejemplos ganadores se inyectan automáticamente en el prompt de las siguientes generaciones (few-shot dinámico).
- Pantalla **Insights** donde el usuario ve qué ha aprendido el sistema sobre su marca y puede activar/desactivar reglas.

---

## Estructura de la app

```text
/                       → Landing pública (qué es, demo, pricing futuro)
/auth                   → Login / Signup (email + Google)
/onboarding             → Asistente de marca (solo primera vez)
/app
  /dashboard            → Resumen: borradores pendientes, posts recientes, insights clave
  /create               → Generar nuevo contenido
  /content              → Biblioteca: borradores, programados, publicados
  /content/:id          → Detalle / editor de un contenido
  /analytics            → Métricas de publicaciones de YouTube
  /insights             → Reglas aprendidas + ejemplos ganadores
  /brand                → Editar perfil de marca, branding, referencias
  /team                 → Miembros e invitaciones
  /settings             → Cuenta, conexión de YouTube
```

---

## Detalles técnicos

**Stack**: React + Vite + Tailwind + shadcn/ui · Lovable Cloud (Supabase) · Lovable AI Gateway (Gemini 3 Flash por defecto, GPT-5 para regeneraciones premium).

**Modelo de datos** (multi-tenant con RLS estricta por `workspace_id`):
- `workspaces` — espacios de marca.
- `workspace_members` — usuario + rol (owner/editor/viewer). Roles en tabla aparte (no en profiles) con función `has_role()` SECURITY DEFINER.
- `brand_profiles` — identidad, estilo, branding, referencias.
- `learning_rules` — reglas extraídas (texto + score + activa sí/no).
- `winning_examples` — contenidos ganadores usados como few-shot.
- `content_drafts` — tipo, red, brief, output JSON estructurado, estado, feedback del usuario.
- `publications` — referencia al draft, video ID en YouTube, fecha publicación.
- `metrics_snapshots` — visitas, likes, watch time, etc. por publicación, capturados periódicamente.
- `social_connections` — tokens OAuth de YouTube cifrados por workspace (access + refresh).

**Edge functions**:
- `generate-content` — construye el prompt con perfil + reglas activas + ejemplos ganadores, llama a Lovable AI con tool calling para devolver JSON estructurado.
- `regenerate-section` — regenera un trozo concreto (un slide, una escena, el hook, el título).
- `youtube-oauth-callback` — completa el flujo OAuth y guarda tokens cifrados.
- `youtube-publish` — sube vídeo + miniatura + metadata vía YouTube Data API v3.
- `sync-youtube-metrics` — cron que cada N horas trae métricas vía YouTube Analytics API.
- `learn-from-results` — cron diario que analiza métricas + feedback, marca ganadores y genera/actualiza reglas usando la IA.

**Conexión a YouTube**:
- App de desarrollador en Google Cloud Console con scopes `youtube.upload`, `youtube.readonly` y `yt-analytics.readonly`.
- Flujo OAuth por usuario (cada miembro autoriza su propio canal).
- Tokens cifrados en `social_connections`, refresh automático.
- Cuotas: la API tiene límite diario de unidades; cada upload cuesta ~1600 unidades. Vigilamos consumo y mostramos al usuario si está cerca del límite.

**Aprendizaje**:
- MVP usa **prompt dinámico + reglas explícitas** (no fine-tuning).
- Las reglas se generan llamando a la IA con: "Aquí están los últimos 20 vídeos del usuario y su rendimiento. Extrae 3-5 reglas accionables sobre qué funciona". Output estructurado vía tool calling.
- Las reglas activas se concatenan al system prompt de generación.

**Seguridad**:
- RLS en todas las tablas filtrando por `workspace_id` y membresía.
- Tokens de YouTube cifrados, nunca expuestos al cliente.
- Validación con Zod en todas las edge functions.

---

## Alcance del MVP (qué entra ahora)

✅ Auth email + Google, espacios de equipo con roles, onboarding de marca.
✅ Generación de Shorts, Carruseles y Posts de texto con IA, editor y regeneración por secciones.
✅ Biblioteca de contenido con estados, feedback 👍/👎 por borrador.
✅ Conexión OAuth con **YouTube**, subida de vídeo + miniatura + metadata, programación.
✅ Pantalla de analytics con métricas reales de YouTube y pantalla de insights con reglas aprendidas editables.
✅ Cron de aprendizaje nocturno.
✅ Documento `plan inicial.md` en la raíz del proyecto al arrancar.

## Fuera de alcance (siguientes iteraciones)

- Pagos/planes de suscripción (Stripe).
- TikTok, Instagram, LinkedIn, X (multi-red).
- Generación del archivo de vídeo final con IA (de momento solo guion + sugerencias visuales; el usuario sube su MP4).
- Generación de imágenes para carruseles y miniaturas (se puede añadir rápido en v2 con Gemini Image).
- Newsletters, blog.
- Fine-tuning real por usuario.
