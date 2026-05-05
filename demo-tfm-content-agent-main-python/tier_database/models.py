"""
Modelos Django que replican el esquema de Supabase.
Permiten usar Django ORM con PostgreSQL local en lugar de Supabase.

Para activar: añadir 'tier_database' a INSTALLED_APPS y configurar DATABASES.
"""
import uuid
from django.db import models


# ── Enumeraciones ─────────────────────────────────────────────

class NewsInteractionType(models.TextChoices):
    SAVED     = "saved",     "Guardada"
    DISMISSED = "dismissed", "Descartada"
    USED      = "used",      "Usada"


class AppRole(models.TextChoices):
    ADMIN = "admin", "Administrador"
    USER  = "user",  "Usuario"


class TeamRole(models.TextChoices):
    OWNER  = "owner",  "Propietario"
    ADMIN  = "admin",  "Administrador"
    EDITOR = "editor", "Editor"
    VIEWER = "viewer", "Visor"


class InvitationStatus(models.TextChoices):
    PENDING  = "pending",  "Pendiente"
    ACCEPTED = "accepted", "Aceptada"
    REVOKED  = "revoked",  "Revocada"
    EXPIRED  = "expired",  "Expirada"


class ContentStatus(models.TextChoices):
    DRAFT     = "draft",     "Borrador"
    PUBLISHED = "published", "Publicado"
    DISCARDED = "discarded", "Descartado"


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", "En prueba"
    ACTIVE   = "active",   "Activa"
    CANCELED = "canceled", "Cancelada"
    PAST_DUE = "past_due", "Pago vencido"
    PAUSED   = "paused",   "Pausada"


class BillingInterval(models.TextChoices):
    MONTHLY = "monthly", "Mensual"
    YEARLY  = "yearly",  "Anual"


class PaymentStatus(models.TextChoices):
    SUCCEEDED = "succeeded", "Realizado"
    PENDING   = "pending",   "Pendiente"
    FAILED    = "failed",    "Fallido"
    REFUNDED  = "refunded",  "Reembolsado"


# ══════════════════════════════════════════════════════════════
#  GRUPO: NOTICIAS & TENDENCIAS
# ══════════════════════════════════════════════════════════════

class NewsItem(models.Model):
    """
    Caché de noticias obtenidas de Google News RSS.
    Cada usuario tiene sus propios registros (aislados por user_id).
    La deduplicación se hace por (user_id, source_url).
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id       = models.UUIDField(db_index=True, help_text="UUID del usuario propietario")
    workspace_id  = models.UUIDField(null=True, blank=True, help_text="Workspace (multi-tenant, opcional)")
    title         = models.TextField(help_text="Titular mejorado por IA")
    summary       = models.TextField(blank=True, default="", help_text="Resumen en una frase (IA)")
    source_url    = models.TextField(help_text="URL de la noticia original")
    source_name   = models.TextField(blank=True, default="", help_text="Nombre del medio")
    published_at  = models.DateTimeField(null=True, blank=True, help_text="Fecha de publicación original")
    topic         = models.TextField(default="otro", help_text="Categoría: tecnologia, ia, marketing…")
    language      = models.CharField(max_length=10, default="es", help_text="Idioma: es | en")
    raw           = models.JSONField(null=True, blank=True, help_text="Datos completos del RSS en crudo")
    fetched_at    = models.DateTimeField(auto_now_add=True, help_text="Fecha de captura")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_items"
        unique_together = [("user_id", "source_url")]
        indexes = [
            models.Index(fields=["user_id", "-fetched_at"], name="idx_news_items_user"),
        ]


class NewsInteraction(models.Model):
    """
    Registro de interacciones del usuario con cada noticia.
    Actualiza dinámicamente las puntuaciones de temas para personalizar el feed.
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id      = models.UUIDField(db_index=True)
    news_item    = models.ForeignKey(
        NewsItem, on_delete=models.CASCADE,
        db_column="news_item_id", related_name="interactions"
    )
    interaction  = models.CharField(
        max_length=20, choices=NewsInteractionType.choices,
        help_text="Tipo: saved | dismissed | used"
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_interactions"
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="idx_news_interactions_user"),
        ]


# ══════════════════════════════════════════════════════════════
#  GRUPO: CONTENIDO GENERADO
# ══════════════════════════════════════════════════════════════

class Content(models.Model):
    """
    Contenido generado por la IA para cada usuario.
    Soporta 4 formatos: short, carousel, post, thread.
    El campo metadata guarda la estructura enriquecida.
    """
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id        = models.UUIDField(db_index=True)
    title          = models.TextField(help_text="Título descriptivo")
    body           = models.TextField(help_text="Texto plano del contenido")
    format         = models.CharField(max_length=20, default="post",
                                      help_text="Formato: short | carousel | post | thread")
    topic          = models.TextField(blank=True, default="")
    tone           = models.TextField(blank=True, default="")
    status         = models.CharField(
        max_length=20, choices=ContentStatus.choices, default=ContentStatus.DRAFT
    )
    source_news    = models.ForeignKey(
        NewsItem, null=True, blank=True, on_delete=models.SET_NULL,
        db_column="source_news_id", related_name="contents"
    )
    metadata       = models.JSONField(default=dict, blank=True,
                                      help_text="Estructura IA: beats, slides, tweets…")
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contents"
        indexes = [
            models.Index(fields=["user_id", "status", "-updated_at"], name="contents_user_status_idx"),
        ]


# ══════════════════════════════════════════════════════════════
#  GRUPO: GESTIÓN DE EQUIPOS
# ══════════════════════════════════════════════════════════════

class TeamMember(models.Model):
    """Miembros reales de un equipo con roles diferenciados."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id   = models.UUIDField(db_index=True, help_text="Propietario del equipo")
    member_id  = models.UUIDField(help_text="Usuario miembro")
    role       = models.CharField(
        max_length=20, choices=TeamRole.choices, default=TeamRole.EDITOR
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "team_members"
        unique_together = [("owner_id", "member_id")]


class TeamInvitation(models.Model):
    """Invitaciones pendientes con expiración de 7 días."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id   = models.UUIDField(db_index=True, help_text="Quien envía la invitación")
    email      = models.EmailField(help_text="Email del invitado")
    role       = models.CharField(
        max_length=20, choices=TeamRole.choices, default=TeamRole.EDITOR
    )
    status     = models.CharField(
        max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    token      = models.TextField(unique=True, help_text="Token hexadecimal de verificación")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Expiración (created_at + 7 días)")

    class Meta:
        db_table = "team_invitations"


# ══════════════════════════════════════════════════════════════
#  GRUPO: ROLES & SEGURIDAD
# ══════════════════════════════════════════════════════════════

class UserRole(models.Model):
    """Rol global del usuario en la plataforma (admin o user)."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id    = models.UUIDField(unique=True, help_text="UUID del usuario")
    role       = models.CharField(max_length=20, choices=AppRole.choices, default=AppRole.USER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_roles"


class UserBan(models.Model):
    """Lista de usuarios baneados. Bloquea todas las generaciones de IA."""
    user_id    = models.UUIDField(primary_key=True, help_text="Usuario baneado")
    reason     = models.TextField(blank=True, default="", help_text="Motivo del baneo")
    banned_by  = models.UUIDField(null=True, blank=True, help_text="Admin que aplicó el baneo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_bans"


class AdminAuditLog(models.Model):
    """Registro inmutable de todas las acciones de administradores."""
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_id          = models.UUIDField(db_index=True)
    admin_email       = models.TextField(blank=True, default="")
    target_user_id    = models.UUIDField(null=True, blank=True, db_index=True)
    target_user_email = models.TextField(blank=True, default="")
    action            = models.TextField(db_index=True,
                                         help_text="Acción: ban_user, set_admin, delete_content…")
    payload           = models.JSONField(default=dict, blank=True)
    result            = models.JSONField(default=dict, blank=True)
    success           = models.BooleanField(default=True)
    error_message     = models.TextField(blank=True, default="")
    ip_address        = models.TextField(blank=True, default="")
    user_agent        = models.TextField(blank=True, default="")
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "admin_audit_logs"
        ordering = ["-created_at"]


# ══════════════════════════════════════════════════════════════
#  GRUPO: IA & CUOTAS
# ══════════════════════════════════════════════════════════════

class AIUsageLog(models.Model):
    """Log de todas las llamadas a la IA (Gemini/Lovable)."""
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id           = models.UUIDField(db_index=True)
    function_name     = models.TextField(help_text="Función: generate-content, generate-insights")
    model             = models.TextField(help_text="Modelo: gemini-2.5-flash, gemini-2.5-pro")
    kind              = models.CharField(max_length=20, default="content",
                                         help_text="Tipo: content | image")
    tokens_in         = models.IntegerField(default=0, help_text="Tokens de entrada (prompt)")
    tokens_out        = models.IntegerField(default=0, help_text="Tokens de salida (respuesta)")
    images_count      = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    success           = models.BooleanField(default=True)
    error_message     = models.TextField(blank=True, default="")
    metadata          = models.JSONField(default=dict, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ai_usage_logs"
        ordering = ["-created_at"]


class UserQuota(models.Model):
    """Límites personalizados por usuario. Sin registro = valores por defecto del código."""
    user_id               = models.UUIDField(primary_key=True)
    daily_content_limit   = models.IntegerField(default=50)
    daily_image_limit     = models.IntegerField(default=30)
    monthly_content_limit = models.IntegerField(default=1000)
    monthly_image_limit   = models.IntegerField(default=500)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_quotas"


# ══════════════════════════════════════════════════════════════
#  GRUPO: FACTURACIÓN
# ══════════════════════════════════════════════════════════════

class Plan(models.Model):
    """Catálogo de planes: Free, Pro, Business."""
    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key                   = models.CharField(max_length=50, unique=True,
                                             help_text="Clave: free, pro, business")
    name                  = models.CharField(max_length=100)
    description           = models.TextField(blank=True, default="")
    price_monthly_cents   = models.IntegerField(default=0)
    price_yearly_cents    = models.IntegerField(default=0)
    currency              = models.CharField(max_length=3, default="EUR")
    monthly_credits       = models.IntegerField(default=0)
    monthly_image_credits = models.IntegerField(default=0)
    features              = models.JSONField(default=list, blank=True)
    active                = models.BooleanField(default=True)
    sort_order            = models.IntegerField(default=0)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plans"
        ordering = ["sort_order"]


class CreditPack(models.Model):
    """Paquetes de créditos adicionales: Starter, Boost, Mega."""
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key           = models.CharField(max_length=50, unique=True)
    name          = models.CharField(max_length=100)
    credits       = models.IntegerField(help_text="Créditos de contenido")
    image_credits = models.IntegerField(default=0)
    price_cents   = models.IntegerField()
    currency      = models.CharField(max_length=3, default="EUR")
    active        = models.BooleanField(default=True)
    sort_order    = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "credit_packs"
        ordering = ["sort_order"]


class Subscription(models.Model):
    """Suscripciones activas de usuarios a planes."""
    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id              = models.UUIDField(db_index=True)
    plan                 = models.ForeignKey(Plan, on_delete=models.PROTECT,
                                             db_column="plan_id", related_name="subscriptions")
    status               = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE,
        db_index=True
    )
    interval             = models.CharField(
        max_length=10, choices=BillingInterval.choices, default=BillingInterval.MONTHLY
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end   = models.DateTimeField(null=True, blank=True)
    canceled_at          = models.DateTimeField(null=True, blank=True)
    trial_end            = models.DateTimeField(null=True, blank=True)
    external_id          = models.TextField(blank=True, default="",
                                            help_text="ID en el proveedor de pagos (Stripe, etc.)")
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"


class Payment(models.Model):
    """Historial de pagos realizados."""
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id         = models.UUIDField(db_index=True)
    subscription    = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL,
        db_column="subscription_id", related_name="payments"
    )
    amount_cents    = models.IntegerField()
    currency        = models.CharField(max_length=3, default="EUR")
    status          = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.SUCCEEDED
    )
    reason          = models.CharField(max_length=30, default="subscription",
                                       help_text="subscription | credit_pack | manual")
    description     = models.TextField(blank=True, default="")
    external_id     = models.TextField(blank=True, default="")
    metadata        = models.JSONField(default=dict, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]


class CreditPurchase(models.Model):
    """Registro de compras de paquetes de créditos adicionales."""
    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id              = models.UUIDField(db_index=True)
    pack                 = models.ForeignKey(
        CreditPack, on_delete=models.PROTECT,
        db_column="pack_id", related_name="purchases"
    )
    payment              = models.ForeignKey(
        Payment, on_delete=models.PROTECT,
        db_column="payment_id", related_name="credit_purchases"
    )
    credits_granted      = models.IntegerField()
    image_credits_granted = models.IntegerField(default=0)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "credit_purchases"


# ══════════════════════════════════════════════════════════════
#  GRUPO: CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

class AppSetting(models.Model):
    """Configuración global clave-valor editable solo por admins."""
    key        = models.CharField(max_length=100, primary_key=True,
                                  help_text="Clave: maintenance_mode, global_banner, default_models")
    value      = models.JSONField(help_text="Valor en formato JSON")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "app_settings"
