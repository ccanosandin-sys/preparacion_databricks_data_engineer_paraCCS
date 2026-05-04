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
- Feedback rápido del usuario en cada borrador: 👍 / 👎 + comentario opcional. Esto alimenta el aprendizaje aunque no se llegue a publicar.

### 5. Publicación y métricas (YouTube)
- Conexión OAuth con la cuenta de YouTube del usuario (canal específico si tiene varios).
- Subida del archivo de vídeo final + título + descripción + tags + miniatura desde la propia interfaz.
- Publicar ahora o programar fecha/hora.
- Pestaña **Analytics**: lista de publicaciones con visitas, likes, comentarios, shares, watch time, retención media, CTR de miniatura.

### 6. Aprendizaje automático por usuario
Cada marca tiene un **perfil de aprendizaje** que se actualiza solo:
- Cuando un Short supera el rendimiento medio del usuario, se marca como **ganador**.
- Cuando recibe 👎 o se descarta, se marca como **señal negativa**.
- Un proceso periódico (cada noche) analiza los ganadores y extrae **reglas explícitas**.
- Estas reglas + 3-5 ejemplos ganadores se inyectan automáticamente en el prompt de las siguientes generaciones (few-shot dinámico).
- Pantalla **Insights** donde el usuario ve qué ha aprendido el sistema y puede activar/desactivar reglas.

---

## Estructura de la app

```
/                       → Landing pública
/auth                   → Login / Signup (email + Google)
/onboarding             → Asistente de marca (solo primera vez)
/app
  /dashboard            → Resumen
  /create               → Generar nuevo contenido
  /content              → Biblioteca: borradores, programados, publicados
  /content/:id          → Detalle / editor
  /analytics            → Métricas de YouTube
  /insights             → Reglas aprendidas
  /brand                → Editar perfil de marca
  /team                 → Miembros e invitaciones
  /settings             → Cuenta, conexión de YouTube
```

---

## Detalles técnicos

**Stack**: React + Vite + Tailwind + shadcn/ui · Lovable Cloud · Lovable AI Gateway (Gemini 3 Flash por defecto, GPT-5 para regeneraciones premium).

**Modelo de datos** (multi-tenant con RLS por `workspace_id`):
- `workspaces`, `workspace_members` (roles en tabla aparte con `has_role()` SECURITY DEFINER)
- `brand_profiles`, `learning_rules`, `winning_examples`
- `content_drafts`, `publications`, `metrics_snapshots`
- `social_connections` (tokens OAuth de YouTube cifrados)

**Edge functions**:
- `generate-content`, `regenerate-section`
- `youtube-oauth-callback`, `youtube-publish`
- `sync-youtube-metrics` (cron), `learn-from-results` (cron diario)

**Conexión a YouTube**:
- App en Google Cloud Console con scopes `youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`.
- OAuth por usuario, tokens cifrados, refresh automático.
- Vigilamos cuotas (cada upload ~1600 unidades).

**Aprendizaje**: prompt dinámico + reglas explícitas extraídas con IA vía tool calling (no fine-tuning).

**Seguridad**: RLS estricta por workspace, tokens cifrados, validación con Zod en edge functions.

---

## Alcance del MVP

✅ Auth email + Google, espacios de equipo con roles, onboarding de marca.
✅ Generación de Shorts, Carruseles y Posts de texto, editor y regeneración por secciones.
✅ Biblioteca con estados, feedback 👍/👎.
✅ Conexión OAuth con YouTube, subida + programación.
✅ Analytics y Insights con reglas editables.
✅ Cron de aprendizaje nocturno.

## Fuera de alcance (siguientes iteraciones)

- Pagos / Stripe
- TikTok, Instagram, LinkedIn, X
- Generación del MP4 final con IA (de momento solo guion)
- Generación de imágenes para carruseles y miniaturas
- Newsletters, blog
- Fine-tuning real
