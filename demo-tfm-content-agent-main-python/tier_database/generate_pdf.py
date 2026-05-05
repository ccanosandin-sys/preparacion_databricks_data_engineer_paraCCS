"""
Generador del diagrama de base de datos y documentación en PDF.
Ejecutar: python tier_database/generate_pdf.py
"""

import os
import sys

# Asegurar que el path del proyecto esté disponible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

# ── Paleta de colores ─────────────────────────────────────────
C_PURPLE     = colors.HexColor("#7c3aed")
C_PURPLE_L   = colors.HexColor("#ede9fe")
C_BLUE       = colors.HexColor("#2563eb")
C_BLUE_L     = colors.HexColor("#dbeafe")
C_GREEN      = colors.HexColor("#059669")
C_GREEN_L    = colors.HexColor("#d1fae5")
C_ORANGE     = colors.HexColor("#d97706")
C_ORANGE_L   = colors.HexColor("#fef3c7")
C_RED        = colors.HexColor("#dc2626")
C_RED_L      = colors.HexColor("#fee2e2")
C_PINK       = colors.HexColor("#db2777")
C_PINK_L     = colors.HexColor("#fce7f3")
C_GRAY       = colors.HexColor("#6b7280")
C_GRAY_L     = colors.HexColor("#f3f4f6")
C_DARK       = colors.HexColor("#111827")
C_WHITE      = colors.white

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "diagrama_base_datos.pdf"
)

# ══════════════════════════════════════════════════════════════
#  DATOS DEL SCHEMA
# ══════════════════════════════════════════════════════════════

TABLES = {
    # ── Grupo: Auth (externo) ──────────────────────────────
    "auth.users": {
        "grupo": "Auth (Supabase)",
        "color": (C_GRAY, C_GRAY_L),
        "descripcion": "Tabla de autenticación gestionada por Supabase Auth. Almacena credenciales y metadatos de sesión de todos los usuarios registrados en la plataforma.",
        "donde_se_usa": "Referenciada (FK) desde todas las tablas del dominio mediante el campo user_id.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único del usuario (auth token)"),
            ("email",         "VARCHAR",       "",    "Dirección de correo electrónico"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de registro"),
            ("last_sign_in",  "TIMESTAMPTZ",   "",    "Último inicio de sesión"),
        ],
    },

    # ── Grupo: Noticias ────────────────────────────────────
    "news_items": {
        "grupo": "Noticias & Tendencias",
        "color": (C_BLUE, C_BLUE_L),
        "descripcion": "Caché de noticias obtenidas de Google News RSS. Cada usuario tiene sus propios registros (aislados por user_id). La deduplicación se hace por (user_id, source_url).",
        "donde_se_usa": "Leída en trends_page, rank-news API y generate-content. Escrita en fetch-news API. Referenciada desde contents (source_news_id) y news_interactions.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único de la noticia"),
            ("user_id",       "UUID",          "FK→auth.users", "Propietario (usuario que buscó la noticia)"),
            ("workspace_id",  "UUID",          "",    "Workspace opcional (multi-tenant)"),
            ("title",         "TEXT",          "",    "Titular de la noticia (mejorado por IA)"),
            ("summary",       "TEXT",          "",    "Resumen en una frase generado por IA"),
            ("source_url",    "TEXT",          "UQ",  "URL de la noticia original"),
            ("source_name",   "TEXT",          "",    "Nombre del medio de comunicación"),
            ("published_at",  "TIMESTAMPTZ",   "",    "Fecha de publicación original"),
            ("topic",         "TEXT",          "",    "Categoría: tecnologia, ia, marketing…"),
            ("language",      "TEXT",          "",    "Idioma: 'es' o 'en' (default: es)"),
            ("raw",           "JSONB",         "",    "Datos completos del RSS en crudo"),
            ("fetched_at",    "TIMESTAMPTZ",   "",    "Fecha en que se capturó la noticia"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de inserción en BD"),
        ],
    },
    "news_interactions": {
        "grupo": "Noticias & Tendencias",
        "color": (C_BLUE, C_BLUE_L),
        "descripcion": "Registro de interacciones del usuario con cada noticia. Una interacción actualiza dinámicamente las puntuaciones de temas (user_topic_scores VIEW) para personalizar el feed.",
        "donde_se_usa": "Escrita en news-interaction API. Leída en analytics API y rank-news API para calcular puntuaciones de topics.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único"),
            ("user_id",       "UUID",          "FK→auth.users", "Usuario que interactuó"),
            ("news_item_id",  "UUID",          "FK→news_items", "Noticia con la que interactuó"),
            ("interaction",   "ENUM",          "",    "Tipo: saved | dismissed | used"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de la interacción"),
        ],
    },
    "user_topic_scores": {
        "grupo": "Noticias & Tendencias",
        "color": (C_BLUE, C_BLUE_L),
        "descripcion": "Vista calculada (VIEW, no tabla física). Agrega puntuaciones por topic para personalizar el ranking de noticias. Fórmula: saved=+2, used=+3, dismissed=-1.",
        "donde_se_usa": "Leída en rank-news API para ordenar noticias y construir el boost_prompt enviado a la IA.",
        "campos": [
            ("user_id",       "UUID",          "→auth.users", "Usuario al que pertenece la puntuación"),
            ("topic",         "TEXT",          "",    "Categoría temática"),
            ("score",         "NUMERIC",       "",    "Puntuación acumulada (mayor = más interés)"),
        ],
    },

    # ── Grupo: Contenidos ──────────────────────────────────
    "contents": {
        "grupo": "Contenido Generado",
        "color": (C_PURPLE, C_PURPLE_L),
        "descripcion": "Almacena todo el contenido generado por la IA para cada usuario. Soporta 4 formatos: short, carousel, post, thread. El campo metadata guarda la estructura enriquecida (JSON con beats, slides, tweets…).",
        "donde_se_usa": "Escrita en generate-content y save-content API. Leída en library_page, analytics API, dashboard. El admin puede ver todos los contenidos.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único del contenido"),
            ("user_id",       "UUID",          "FK→auth.users", "Creador del contenido"),
            ("title",         "TEXT",          "",    "Título descriptivo dado por el usuario"),
            ("body",          "TEXT",          "",    "Texto plano del contenido generado"),
            ("format",        "TEXT",          "",    "Formato: short | carousel | post | thread"),
            ("topic",         "TEXT",          "",    "Tema sobre el que trata"),
            ("tone",          "TEXT",          "",    "Tono: profesional, educativo, coloquial…"),
            ("status",        "ENUM",          "",    "Estado: draft | published | discarded"),
            ("source_news_id","UUID",          "FK→news_items", "Noticia de origen (opcional)"),
            ("metadata",      "JSONB",         "",    "Estructura IA: beats, slides, tweets…"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de creación"),
            ("updated_at",    "TIMESTAMPTZ",   "",    "Última modificación (auto-actualizado)"),
        ],
    },

    # ── Grupo: Equipo ──────────────────────────────────────
    "team_members": {
        "grupo": "Gestión de Equipos",
        "color": (C_GREEN, C_GREEN_L),
        "descripcion": "Miembros reales de un equipo. El owner_id es el usuario que creó el equipo. member_id es el usuario invitado. El rol define permisos dentro del equipo.",
        "donde_se_usa": "CRUD completo en team API. Consultada en views de equipo para mostrar colaboradores.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único del registro"),
            ("owner_id",      "UUID",          "FK→auth.users", "Propietario del equipo"),
            ("member_id",     "UUID",          "FK→auth.users", "Usuario miembro"),
            ("role",          "ENUM",          "",    "Rol: owner | admin | editor | viewer"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de incorporación al equipo"),
        ],
    },
    "team_invitations": {
        "grupo": "Gestión de Equipos",
        "color": (C_GREEN, C_GREEN_L),
        "descripcion": "Invitaciones pendientes para unirse a un equipo. El token es único por invitación. Las invitaciones expiran en 7 días. Un mismo email solo puede tener una invitación pending.",
        "donde_se_usa": "Creada en invite-member API. Consultada y actualizada en team API. El usuario invitado la acepta mediante un link.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único"),
            ("owner_id",      "UUID",          "FK→auth.users", "Quien envía la invitación"),
            ("email",         "TEXT",          "",    "Email del invitado"),
            ("role",          "ENUM",          "",    "Rol asignado al aceptar: editor (default)"),
            ("status",        "ENUM",          "",    "Estado: pending | accepted | revoked | expired"),
            ("token",         "TEXT",          "UQ",  "Token hexadecimal de verificación"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de creación"),
            ("expires_at",    "TIMESTAMPTZ",   "",    "Expiración (created_at + 7 días)"),
        ],
    },

    # ── Grupo: Roles & Seguridad ───────────────────────────
    "user_roles": {
        "grupo": "Roles & Seguridad",
        "color": (C_RED, C_RED_L),
        "descripcion": "Define el rol global de cada usuario en la plataforma (admin o user). Se consulta en todas las verificaciones de administrador. La función has_role() es SECURITY DEFINER para evitar recursión en RLS.",
        "donde_se_usa": "Consultada en _require_admin() de admin API, _is_admin() de views, overview API.",
        "campos": [
            ("id",            "UUID",          "PK",  "Identificador único"),
            ("user_id",       "UUID",          "FK→auth.users", "Usuario al que se asigna el rol"),
            ("role",          "ENUM",          "",    "Rol: admin | user"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha de asignación del rol"),
        ],
    },
    "user_bans": {
        "grupo": "Roles & Seguridad",
        "color": (C_RED, C_RED_L),
        "descripcion": "Lista de usuarios baneados. Si el user_id aparece aquí, check_quota() bloquea todas las generaciones de IA. El admin puede banear/desbanear desde el panel.",
        "donde_se_usa": "Consultada en check_quota() de quota_service antes de cada generación. Escrita desde ban-user y unban-user API.",
        "campos": [
            ("user_id",       "UUID",          "PK/FK→auth.users", "Usuario baneado"),
            ("reason",        "TEXT",          "",    "Motivo del baneo"),
            ("banned_by",     "UUID",          "",    "Admin que aplicó el baneo"),
            ("created_at",    "TIMESTAMPTZ",   "",    "Fecha del baneo"),
        ],
    },
    "admin_audit_logs": {
        "grupo": "Roles & Seguridad",
        "color": (C_RED, C_RED_L),
        "descripcion": "Registro inmutable de todas las acciones realizadas por administradores. Se inserta automáticamente con _audit_log() después de cada acción admin (ban, set-admin, set-quota, delete-content, etc.).",
        "donde_se_usa": "Escrita en todas las acciones de admin API (_audit_log). Leída en audit-logs API del panel admin.",
        "campos": [
            ("id",                "UUID",        "PK",  "Identificador único"),
            ("admin_id",          "UUID",        "→auth.users", "Admin que realizó la acción"),
            ("admin_email",       "TEXT",        "",    "Email del admin (snapshot)"),
            ("target_user_id",    "UUID",        "→auth.users", "Usuario afectado"),
            ("target_user_email", "TEXT",        "",    "Email del afectado (snapshot)"),
            ("action",            "TEXT",        "",    "Acción: ban_user, set_admin, delete_content…"),
            ("payload",           "JSONB",       "",    "Datos de entrada de la acción"),
            ("result",            "JSONB",       "",    "Resultado: success o error"),
            ("success",           "BOOLEAN",     "",    "Si la acción tuvo éxito"),
            ("error_message",     "TEXT",        "",    "Mensaje de error si falló"),
            ("ip_address",        "TEXT",        "",    "IP del administrador"),
            ("user_agent",        "TEXT",        "",    "Navegador/cliente del admin"),
            ("created_at",        "TIMESTAMPTZ", "",    "Fecha de la acción"),
        ],
    },

    # ── Grupo: IA & Cuotas ─────────────────────────────────
    "ai_usage_logs": {
        "grupo": "IA & Cuotas",
        "color": (C_ORANGE, C_ORANGE_L),
        "descripcion": "Log de todas las llamadas a la IA (Gemini/Lovable). Registra tokens consumidos, coste estimado y si fue exitosa. check_quota() cuenta las filas de hoy para verificar límites diarios.",
        "donde_se_usa": "Escrita en log_ai_usage() de quota_service tras cada generación. Leída en check_quota(), analytics API, ai-logs API del admin.",
        "campos": [
            ("id",               "UUID",        "PK",  "Identificador único"),
            ("user_id",          "UUID",        "FK→auth.users", "Usuario que generó"),
            ("function_name",    "TEXT",        "",    "Función: generate-content, generate-insights"),
            ("model",            "TEXT",        "",    "Modelo IA: gemini-2.5-flash, gemini-2.5-pro"),
            ("kind",             "TEXT",        "",    "Tipo: content | image"),
            ("tokens_in",        "INTEGER",     "",    "Tokens de entrada (prompt)"),
            ("tokens_out",       "INTEGER",     "",    "Tokens de salida (respuesta)"),
            ("images_count",     "INTEGER",     "",    "Imágenes generadas (si aplica)"),
            ("estimated_cost_usd","NUMERIC",    "",    "Coste estimado en USD"),
            ("success",          "BOOLEAN",     "",    "Si la llamada fue exitosa"),
            ("error_message",    "TEXT",        "",    "Mensaje de error si falló"),
            ("metadata",         "JSONB",       "",    "Contexto adicional: formato, topic…"),
            ("created_at",       "TIMESTAMPTZ", "",    "Fecha de la llamada"),
        ],
    },
    "user_quotas": {
        "grupo": "IA & Cuotas",
        "color": (C_ORANGE, C_ORANGE_L),
        "descripcion": "Límites personalizados por usuario. Si no existe registro para un usuario se aplican los valores por defecto del código (50/día contenido, 20/día imagen). El admin puede ajustar estos límites.",
        "donde_se_usa": "Leída en check_quota() de quota_service. Escrita en set-quota API del admin.",
        "campos": [
            ("user_id",              "UUID",    "PK/FK→auth.users", "Usuario al que aplican las cuotas"),
            ("daily_content_limit",  "INTEGER", "",    "Máximo de contenidos por día (default 50)"),
            ("daily_image_limit",    "INTEGER", "",    "Máximo de imágenes por día (default 30)"),
            ("monthly_content_limit","INTEGER", "",    "Máximo de contenidos por mes (default 1000)"),
            ("monthly_image_limit",  "INTEGER", "",    "Máximo de imágenes por mes (default 500)"),
            ("created_at",           "TIMESTAMPTZ","","Fecha de creación"),
            ("updated_at",           "TIMESTAMPTZ","","Última actualización (auto-trigger)"),
        ],
    },

    # ── Grupo: Facturación ─────────────────────────────────
    "plans": {
        "grupo": "Facturación",
        "color": (C_PINK, C_PINK_L),
        "descripcion": "Catálogo de planes de suscripción: Free, Pro, Business. Incluye precios mensuales y anuales, créditos mensuales de contenido e imagen, y features en JSON.",
        "donde_se_usa": "Leída en página de precios/planes. Referenciada desde subscriptions.",
        "campos": [
            ("id",                    "UUID",    "PK",  "Identificador único"),
            ("key",                   "TEXT",    "UQ",  "Clave: free, pro, business"),
            ("name",                  "TEXT",    "",    "Nombre visible: Free, Pro, Business"),
            ("description",           "TEXT",    "",    "Descripción del plan"),
            ("price_monthly_cents",   "INTEGER", "",    "Precio mensual en céntimos (0=gratis)"),
            ("price_yearly_cents",    "INTEGER", "",    "Precio anual en céntimos"),
            ("currency",              "TEXT",    "",    "Moneda: EUR (default)"),
            ("monthly_credits",       "INTEGER", "",    "Créditos de contenido por mes"),
            ("monthly_image_credits", "INTEGER", "",    "Créditos de imagen por mes"),
            ("features",              "JSONB",   "",    "Lista de características del plan"),
            ("active",                "BOOLEAN", "",    "Si el plan está disponible"),
            ("sort_order",            "INTEGER", "",    "Orden de visualización"),
            ("created_at",            "TIMESTAMPTZ","","Fecha de creación"),
            ("updated_at",            "TIMESTAMPTZ","","Última actualización"),
        ],
    },
    "credit_packs": {
        "grupo": "Facturación",
        "color": (C_PINK, C_PINK_L),
        "descripcion": "Paquetes de créditos adicionales que se pueden comprar puntualmente: Starter (100), Boost (500), Mega (2000). Cada pack tiene créditos de contenido e imagen.",
        "donde_se_usa": "Referenciada desde credit_purchases. Leída en página de compra de créditos.",
        "campos": [
            ("id",             "UUID",    "PK",  "Identificador único"),
            ("key",            "TEXT",    "UQ",  "Clave: starter, boost, mega"),
            ("name",           "TEXT",    "",    "Nombre visible"),
            ("credits",        "INTEGER", "",    "Créditos de contenido incluidos"),
            ("image_credits",  "INTEGER", "",    "Créditos de imagen incluidos"),
            ("price_cents",    "INTEGER", "",    "Precio en céntimos de euro"),
            ("currency",       "TEXT",    "",    "Moneda: EUR"),
            ("active",         "BOOLEAN", "",    "Si el pack está disponible"),
            ("sort_order",     "INTEGER", "",    "Orden de visualización"),
            ("created_at",     "TIMESTAMPTZ","","Fecha de creación"),
        ],
    },
    "subscriptions": {
        "grupo": "Facturación",
        "color": (C_PINK, C_PINK_L),
        "descripcion": "Suscripciones activas de usuarios a planes. Gestiona el ciclo de facturación (start/end), estado (trialing, active, canceled…) y el identificador externo del proveedor de pagos.",
        "donde_se_usa": "Leída en perfil de usuario para mostrar plan activo. Referenciada desde payments.",
        "campos": [
            ("id",                   "UUID",    "PK",  "Identificador único"),
            ("user_id",              "UUID",    "FK→auth.users", "Suscriptor"),
            ("plan_id",              "UUID",    "FK→plans", "Plan contratado"),
            ("status",               "ENUM",    "",    "Estado: trialing|active|canceled|past_due|paused"),
            ("interval",             "ENUM",    "",    "Ciclo: monthly | yearly"),
            ("current_period_start", "TIMESTAMPTZ","","Inicio del período actual"),
            ("current_period_end",   "TIMESTAMPTZ","","Fin del período actual"),
            ("canceled_at",          "TIMESTAMPTZ","","Fecha de cancelación"),
            ("trial_end",            "TIMESTAMPTZ","","Fin del período de prueba"),
            ("external_id",          "TEXT",    "",    "ID en el proveedor de pagos (Stripe, etc.)"),
            ("created_at",           "TIMESTAMPTZ","","Fecha de creación"),
            ("updated_at",           "TIMESTAMPTZ","","Última actualización"),
        ],
    },
    "payments": {
        "grupo": "Facturación",
        "color": (C_PINK, C_PINK_L),
        "descripcion": "Historial de pagos realizados. Puede ser por suscripción, compra de créditos adicionales o ajuste manual. El status refleja el resultado del procesador de pagos.",
        "donde_se_usa": "Leída en historial de facturación del usuario. Referenciada desde credit_purchases.",
        "campos": [
            ("id",              "UUID",    "PK",  "Identificador único"),
            ("user_id",         "UUID",    "FK→auth.users", "Usuario que pagó"),
            ("subscription_id", "UUID",    "FK→subscriptions", "Suscripción asociada (si aplica)"),
            ("amount_cents",    "INTEGER", "",    "Importe en céntimos"),
            ("currency",        "TEXT",    "",    "Moneda: EUR"),
            ("status",          "ENUM",    "",    "Estado: succeeded|pending|failed|refunded"),
            ("reason",          "TEXT",    "",    "Motivo: subscription|credit_pack|manual"),
            ("description",     "TEXT",    "",    "Descripción del cobro"),
            ("external_id",     "TEXT",    "",    "ID en el proveedor de pagos"),
            ("metadata",        "JSONB",   "",    "Datos adicionales del pago"),
            ("created_at",      "TIMESTAMPTZ","","Fecha del pago"),
        ],
    },
    "credit_purchases": {
        "grupo": "Facturación",
        "color": (C_PINK, C_PINK_L),
        "descripcion": "Registro de compras de paquetes de créditos adicionales. Vincula el pago con el pack adquirido y los créditos concedidos al usuario.",
        "donde_se_usa": "Escrita al confirmar pago de un credit_pack. Leída para mostrar historial de compras.",
        "campos": [
            ("id",                   "UUID",    "PK",  "Identificador único"),
            ("user_id",              "UUID",    "FK→auth.users", "Comprador"),
            ("pack_id",              "UUID",    "FK→credit_packs", "Pack comprado"),
            ("payment_id",           "UUID",    "FK→payments", "Pago asociado"),
            ("credits_granted",      "INTEGER", "",    "Créditos de contenido concedidos"),
            ("image_credits_granted","INTEGER", "",    "Créditos de imagen concedidos"),
            ("created_at",           "TIMESTAMPTZ","","Fecha de la compra"),
        ],
    },

    # ── Grupo: Configuración ───────────────────────────────
    "app_settings": {
        "grupo": "Configuración",
        "color": (C_GRAY, C_GRAY_L),
        "descripcion": "Configuración global de la aplicación almacenada como clave-valor JSON. Incluye modo mantenimiento, banner global y modelos de IA por defecto. Editable solo por admins.",
        "donde_se_usa": "Leída en get-settings API del admin. Escrita en update-setting API.",
        "campos": [
            ("key",        "TEXT",        "PK",  "Clave: maintenance_mode, global_banner, default_models"),
            ("value",      "JSONB",       "",    "Valor en formato JSON"),
            ("updated_at", "TIMESTAMPTZ", "",    "Última actualización"),
            ("updated_by", "UUID",        "",    "Admin que lo actualizó"),
        ],
    },
}

# ══════════════════════════════════════════════════════════════
#  RELACIONES (para el diagrama)
# ══════════════════════════════════════════════════════════════

RELATIONS = [
    ("news_items",        "auth.users",     "news_items.user_id → auth.users.id"),
    ("news_interactions", "auth.users",     "news_interactions.user_id → auth.users.id"),
    ("news_interactions", "news_items",     "news_interactions.news_item_id → news_items.id"),
    ("contents",          "auth.users",     "contents.user_id → auth.users.id"),
    ("contents",          "news_items",     "contents.source_news_id → news_items.id"),
    ("team_members",      "auth.users",     "team_members.owner_id / member_id → auth.users.id"),
    ("team_invitations",  "auth.users",     "team_invitations.owner_id → auth.users.id"),
    ("user_roles",        "auth.users",     "user_roles.user_id → auth.users.id"),
    ("user_bans",         "auth.users",     "user_bans.user_id → auth.users.id"),
    ("ai_usage_logs",     "auth.users",     "ai_usage_logs.user_id → auth.users.id"),
    ("user_quotas",       "auth.users",     "user_quotas.user_id → auth.users.id"),
    ("subscriptions",     "auth.users",     "subscriptions.user_id → auth.users.id"),
    ("subscriptions",     "plans",          "subscriptions.plan_id → plans.id"),
    ("payments",          "auth.users",     "payments.user_id → auth.users.id"),
    ("payments",          "subscriptions",  "payments.subscription_id → subscriptions.id"),
    ("credit_purchases",  "auth.users",     "credit_purchases.user_id → auth.users.id"),
    ("credit_purchases",  "credit_packs",   "credit_purchases.pack_id → credit_packs.id"),
    ("credit_purchases",  "payments",       "credit_purchases.payment_id → payments.id"),
    ("admin_audit_logs",  "auth.users",     "admin_audit_logs.admin_id → auth.users.id"),
]

# ══════════════════════════════════════════════════════════════
#  FLOWABLE: DIAGRAMA ER DIBUJADO CON CANVAS
# ══════════════════════════════════════════════════════════════

class ERDiagram(Flowable):
    """Dibuja el diagrama entidad-relación."""

    # Posiciones (x, y) de cada tabla en el diagrama (mm)
    POSITIONS = {
        "auth.users":       (85,  195),
        "news_items":       (10,  130),
        "news_interactions":(10,   55),
        "user_topic_scores":(10,    5),
        "contents":         (85,  130),
        "team_members":     (165, 130),
        "team_invitations": (165,  55),
        "user_roles":       (165, 195),
        "user_bans":        (165, 245),
        "admin_audit_logs": (85,  245),
        "ai_usage_logs":    (85,   55),
        "user_quotas":      (85,    5),
        "plans":            (10,  245),
        "credit_packs":     (10,  195),
        "subscriptions":    (10,  305),
        "payments":         (85,  305),
        "credit_purchases": (165, 305),
        "app_settings":     (165,   5),
    }

    BOX_W  = 58    # mm ancho de cada caja (espacio lógico)
    BOX_H  = 14    # mm alto de cada caja (espacio lógico)
    W      = 210   # mm ancho lógico del diagrama
    H      = 340   # mm alto lógico del diagrama
    SCALE  = 0.72  # factor de escala para que quepa en A4 portrait

    def __init__(self):
        super().__init__()
        self.width  = self.W * mm * self.SCALE
        self.height = self.H * mm * self.SCALE

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Escalar todo el dibujo para que quepa en la página
        c.saveState()
        c.scale(self.SCALE, self.SCALE)

        # Fondo
        c.setFillColor(C_GRAY_L)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # Título
        c.setFillColor(C_DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(self.width / 2, self.height - 8 * mm,
                            "Diagrama Entidad-Relación – ContentAgent DB")

        # Dibujar relaciones primero (debajo de los boxes)
        c.setStrokeColor(C_GRAY)
        c.setLineWidth(0.5)
        for src, dst, _ in RELATIONS:
            sx, sy = self.POSITIONS[src]
            dx, dy = self.POSITIONS[dst]
            # Centro del box fuente y destino
            scx = (sx + self.BOX_W / 2) * mm
            scy = (self.H - sy - self.BOX_H / 2) * mm
            dcx = (dx + self.BOX_W / 2) * mm
            dcy = (self.H - dy - self.BOX_H / 2) * mm
            c.line(scx, scy, dcx, dcy)

        # Dibujar cajas de tablas
        grupos_colores = {}
        for t_name, t_data in TABLES.items():
            g = t_data["grupo"]
            col_border, col_fill = t_data["color"]
            grupos_colores[g] = (col_border, col_fill)
            self._draw_box(c, t_name, t_data, self.POSITIONS[t_name])

        # Leyenda de grupos
        lx = 5 * mm
        ly = 10 * mm
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(C_DARK)
        c.drawString(lx, ly + 6 * mm, "Grupos:")
        for i, (grupo, (cb, cf)) in enumerate(grupos_colores.items()):
            c.setFillColor(cf)
            c.setStrokeColor(cb)
            c.setLineWidth(0.8)
            c.rect(lx, ly - i * 5 * mm, 4 * mm, 3 * mm, fill=1, stroke=1)
            c.setFillColor(C_DARK)
            c.setFont("Helvetica", 5.5)
            c.drawString(lx + 5 * mm, ly - i * 5 * mm + 0.8 * mm, grupo)

        c.restoreState()

    def _draw_box(self, c, name, data, pos):
        col_border, col_fill = data["color"]
        x = pos[0] * mm
        y = (self.H - pos[1] - self.BOX_H) * mm
        w = self.BOX_W * mm
        h = self.BOX_H * mm

        # Sombra
        c.setFillColor(colors.HexColor("#e5e7eb"))
        c.rect(x + 1 * mm, y - 1 * mm, w, h, fill=1, stroke=0)

        # Caja principal
        c.setFillColor(col_fill)
        c.setStrokeColor(col_border)
        c.setLineWidth(1.2)
        c.rect(x, y, w, h, fill=1, stroke=1)

        # Barra superior de color
        c.setFillColor(col_border)
        c.rect(x, y + h - 4 * mm, w, 4 * mm, fill=1, stroke=0)

        # Nombre de la tabla
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(x + w / 2, y + h - 2.8 * mm, name)

        # Grupo
        c.setFillColor(col_border)
        c.setFont("Helvetica", 4.5)
        grupo_txt = data["grupo"]
        c.drawCentredString(x + w / 2, y + h - 4 * mm - 2.5 * mm, grupo_txt)

        # Campos clave (PK, FK)
        c.setFillColor(C_DARK)
        c.setFont("Helvetica", 4.5)
        key_fields = [(f, t, k, d) for f, t, k, d in data["campos"] if k]
        y_txt = y + h - 4 * mm - 5 * mm
        for i, (fname, ftype, key, _) in enumerate(key_fields[:4]):
            if y_txt < y + 0.5 * mm:
                break
            prefix = f"[{key[:2]}] " if key else ""
            c.drawString(x + 1.5 * mm, y_txt, f"{prefix}{fname}: {ftype}")
            y_txt -= 2 * mm

        # Indicador si hay más campos
        total = len(data["campos"])
        c.setFont("Helvetica-Oblique", 4)
        c.setFillColor(C_GRAY)
        c.drawString(x + 1.5 * mm, y + 0.8 * mm, f"+ {total} campos totales")


# ══════════════════════════════════════════════════════════════
#  GENERADOR DE PDF
# ══════════════════════════════════════════════════════════════

def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Estilos personalizados
    s_h1 = ParagraphStyle(
        "H1", parent=styles["Title"],
        fontSize=22, textColor=C_PURPLE, spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    s_h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=14, textColor=C_PURPLE, spaceBefore=12, spaceAfter=4,
        fontName="Helvetica-Bold", borderPad=4,
    )
    s_h3 = ParagraphStyle(
        "H3", parent=styles["Heading3"],
        fontSize=11, textColor=C_DARK, spaceBefore=10, spaceAfter=3,
        fontName="Helvetica-Bold",
    )
    s_body = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, leading=13, textColor=C_DARK,
        fontName="Helvetica", spaceAfter=4, alignment=TA_JUSTIFY,
    )
    s_note = ParagraphStyle(
        "Note", parent=styles["Normal"],
        fontSize=8, leading=11, textColor=C_GRAY,
        fontName="Helvetica-Oblique", spaceAfter=6,
    )
    s_label = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=8, textColor=C_PURPLE,
        fontName="Helvetica-Bold",
    )
    s_center = ParagraphStyle(
        "Center", parent=styles["Normal"],
        fontSize=9, alignment=TA_CENTER, textColor=C_GRAY,
    )

    story = []

    # ── PORTADA ───────────────────────────────────────────────
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("ContentAgent", s_h1))
    story.append(Paragraph(
        "Documentación del Esquema de Base de Datos",
        ParagraphStyle("Sub", parent=s_h1, fontSize=14, textColor=C_GRAY, fontName="Helvetica"),
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_PURPLE))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Este documento describe el modelo relacional completo de la plataforma ContentAgent. "
        "Incluye el diagrama entidad-relación, la descripción de cada tabla, sus campos, "
        "tipos de dato, restricciones y el lugar del código donde se utilizan.",
        s_body,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Resumen estadístico
    n_tables = len([k for k in TABLES if "VIEW" not in k and k != "user_topic_scores"])
    n_views  = 1
    n_fields = sum(len(v["campos"]) for v in TABLES.values())
    n_fk     = len(RELATIONS)
    summary_data = [
        ["Tablas físicas", str(n_tables)],
        ["Vistas (VIEW)", str(n_views)],
        ["Campos totales", str(n_fields)],
        ["Relaciones FK", str(n_fk)],
        ["Grupos temáticos", "7"],
        ["Motor BD", "PostgreSQL (Supabase)"],
    ]
    t_summary = Table(summary_data, colWidths=[5 * cm, 4 * cm])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), C_PURPLE_L),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1), C_PURPLE),
        ("TEXTCOLOR",   (1, 0), (1, -1), C_DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_WHITE, C_GRAY_L]),
        ("GRID",        (0, 0), (-1, -1), 0.5, C_GRAY),
        ("PADDING",     (0, 0), (-1, -1), 5),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 0.5 * cm))

    # Grupos temáticos
    story.append(Paragraph("Grupos Temáticos", s_h2))
    grupos = {
        "Auth (Supabase)":        ("auth.users", "Sistema de autenticación gestionado por Supabase. Tabla externa.", C_GRAY),
        "Noticias & Tendencias":  ("news_items, news_interactions, user_topic_scores", "Captura, almacenamiento y ranking personalizado de noticias via Google News RSS.", C_BLUE),
        "Contenido Generado":     ("contents", "Todo el contenido generado por IA: shorts, carruseles, posts y threads.", C_PURPLE),
        "Gestión de Equipos":     ("team_members, team_invitations", "Colaboración: invitaciones y miembros de equipo con roles.", C_GREEN),
        "Roles & Seguridad":      ("user_roles, user_bans, admin_audit_logs", "Control de acceso, bans y auditoría de acciones administrativas.", C_RED),
        "IA & Cuotas":            ("ai_usage_logs, user_quotas", "Registro de consumo de IA y límites personalizados por usuario.", C_ORANGE),
        "Facturación":            ("plans, credit_packs, subscriptions, payments, credit_purchases", "Planes, créditos adicionales, suscripciones y pagos.", C_PINK),
        "Configuración":          ("app_settings", "Parámetros globales de la aplicación editables por el admin.", C_GRAY),
    }
    g_data = [["Grupo", "Tablas", "Descripción"]]
    for g, (tables, desc, col) in grupos.items():
        g_data.append([g, tables, desc])
    t_g = Table(g_data, colWidths=[3.5 * cm, 4.5 * cm, 7.5 * cm])
    t_g.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), C_PURPLE),
        ("TEXTCOLOR",   (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAY_L]),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_GRAY),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_g)
    story.append(PageBreak())

    # ── DIAGRAMA ER ───────────────────────────────────────────
    story.append(Paragraph("Diagrama Entidad-Relación", s_h1))
    story.append(Paragraph(
        "Representación visual del modelo de datos. Las líneas representan relaciones de "
        "clave foránea (FK). Los colores identifican el grupo temático de cada tabla.",
        s_body,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(ERDiagram())
    story.append(Spacer(1, 0.3 * cm))

    # Tabla de relaciones
    story.append(Paragraph("Relaciones (Claves Foráneas)", s_h2))
    rel_data = [["Tabla origen", "Tabla destino", "Descripción de la FK"]]
    for src, dst, desc in RELATIONS:
        rel_data.append([src, dst, desc])
    t_rel = Table(rel_data, colWidths=[3.5 * cm, 3.5 * cm, 8.5 * cm])
    t_rel.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), C_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BLUE_L]),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_GRAY),
        ("PADDING",     (0, 0), (-1, -1), 3.5),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_rel)
    story.append(PageBreak())

    # ── DOCUMENTACIÓN POR TABLA ───────────────────────────────
    story.append(Paragraph("Documentación Detallada por Tabla", s_h1))
    story.append(Spacer(1, 0.3 * cm))

    grupo_actual = None
    for t_name, t_data in TABLES.items():
        grupo = t_data["grupo"]
        col_border, col_fill = t_data["color"]

        if grupo != grupo_actual:
            grupo_actual = grupo
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(f"── {grupo} ──", ParagraphStyle(
                "GrupHeader", parent=s_h2,
                fontSize=12, textColor=col_border,
                borderPad=4,
            )))

        # Cabecera de tabla
        is_view = t_name == "user_topic_scores"
        tipo_str = "VIEW" if is_view else "TABLE"
        hex_color = col_border.hexval()[2:] if col_border.hexval().startswith("0x") else col_border.hexval()
        story.append(Paragraph(
            f"<font color='#{hex_color}'>{t_name}</font>"
            f"  <font size='8' color='gray'>[{tipo_str}]</font>",
            s_h3,
        ))

        # Descripción
        story.append(Paragraph(t_data["descripcion"], s_body))

        # Dónde se usa
        story.append(Paragraph(
            f"<b>Usado en:</b> {t_data['donde_se_usa']}", s_note,
        ))

        # Tabla de campos
        campo_data = [["Campo", "Tipo", "Restricción", "Descripción"]]
        for fname, ftype, key, desc in t_data["campos"]:
            campo_data.append([fname, ftype, key, desc])

        t_campos = Table(
            campo_data,
            colWidths=[3.0 * cm, 2.5 * cm, 2.2 * cm, 7.8 * cm],
        )
        t_campos.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), col_border),
            ("TEXTCOLOR",    (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, col_fill]),
            ("GRID",         (0, 0), (-1, -1), 0.3, C_GRAY),
            ("PADDING",      (0, 0), (-1, -1), 3.5),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR",    (2, 1), (2, -1), col_border),
            ("FONTNAME",     (2, 1), (2, -1), "Helvetica-Bold"),
        ]))
        story.append(t_campos)
        story.append(Spacer(1, 0.5 * cm))

    # ── INSTRUCCIONES tier_database ───────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Cómo Construir la BD en tier_database", s_h1))
    story.append(Spacer(1, 0.3 * cm))

    install_steps = [
        ("1. Instalar PostgreSQL",
         "Descarga e instala PostgreSQL 15+ desde https://www.postgresql.org/download/. "
         "En Windows puedes usar el instalador o via conda: conda install -c conda-forge postgresql",
         C_BLUE),
        ("2. Instalar psycopg2",
         "pip install psycopg2-binary\n"
         "Este adaptador conecta Django con PostgreSQL.",
         C_GREEN),
        ("3. Instalar django-extensions y pillow (opcional)",
         "pip install django-extensions pillow\n"
         "Permite generar diagramas del modelo con el comando graph_models.",
         C_GREEN),
        ("4. Configurar la conexión en .env",
         "Añade en el fichero .env:\n"
         "DB_NAME=contentagent\nDB_USER=postgres\nDB_PASSWORD=tu_password\n"
         "DB_HOST=localhost\nDB_PORT=5432",
         C_ORANGE),
        ("5. Activar tier_database en Django",
         "En content_agent/settings.py cambia DATABASES para usar PostgreSQL "
         "y añade 'tier_database' a INSTALLED_APPS.",
         C_PURPLE),
        ("6. Ejecutar migraciones",
         "python manage.py makemigrations tier_database\n"
         "python manage.py migrate\n"
         "Esto creará todas las tablas en tu PostgreSQL local.",
         C_RED),
        ("7. Alternativa: usar SQLite para desarrollo",
         "Si no quieres instalar PostgreSQL, cambia ENGINE a "
         "'django.db.backends.sqlite3' y NAME a BASE_DIR / 'db.sqlite3'. "
         "SQLite no necesita instalación adicional.",
         C_GRAY),
    ]

    for title, content, col in install_steps:
        story.append(Paragraph(title, ParagraphStyle(
            "StepTitle", parent=s_h3,
            fontSize=10, textColor=col,
        )))
        story.append(Paragraph(content.replace("\n", "<br/>"), s_body))
        story.append(Spacer(1, 0.2 * cm))

    # Build
    doc.build(story)
    print(f"\nOK - PDF generado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
