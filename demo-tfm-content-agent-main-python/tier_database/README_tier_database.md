# tier_database — Base de Datos Local con Django ORM

Esta carpeta contiene los modelos Django que replican el esquema de Supabase,
permitiendo construir y usar la base de datos localmente con PostgreSQL o SQLite.

## Estructura

```
tier_database/
  models.py              <- Modelos Django (18 tablas documentadas)
  generate_pdf.py        <- Script que genera el diagrama PDF
  diagrama_base_datos.pdf <- Diagrama ER + documentacion completa (ya generado)
  README_tier_database.md <- Este fichero
```

---

## Que instalar para construir la BD localmente

### Opcion A — PostgreSQL (recomendada, identica a Supabase)

**1. Instalar PostgreSQL 15+**

```bash
# Descarga e instalador en: https://www.postgresql.org/download/windows/
# O via conda:
conda install -c conda-forge postgresql
```

**2. Instalar psycopg2 (adaptador Python-PostgreSQL)**

```bash
pip install psycopg2-binary
```

**3. Crear la base de datos**

```sql
-- En psql o pgAdmin:
CREATE DATABASE contentagent;
CREATE USER contentagent_user WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE contentagent TO contentagent_user;
```

**4. Anadir credenciales al .env**

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=contentagent
DB_USER=contentagent_user
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432
```

**5. Actualizar content_agent/settings.py**

```python
import os

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'db.sqlite3'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
    }
}

INSTALLED_APPS = [
    ...
    'tier_database',  # <- anadir esto
]
```

**6. Ejecutar migraciones**

```bash
python manage.py makemigrations tier_database
python manage.py migrate
```

---

### Opcion B — SQLite (sin instalacion, para desarrollo rapido)

SQLite viene incluido con Python. Solo cambia settings.py:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

INSTALLED_APPS = [
    ...
    'tier_database',
]
```

Luego ejecuta:
```bash
python manage.py makemigrations tier_database
python manage.py migrate
```

La BD se crea en el fichero `db.sqlite3` en la raiz del proyecto.

---

### Opcion C — PostgreSQL + pgvector (para busqueda semantica)

Si quieres anadir busqueda semantica de contenidos/noticias:

```bash
pip install pgvector
```

Instala la extension en PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Luego puedes anadir campos vectoriales a los modelos:
```python
from pgvector.django import VectorField

class Content(models.Model):
    ...
    embedding = VectorField(dimensions=1536, null=True)  # OpenAI text-embedding-3-small
```

---

## Resumen de tablas

| Grupo | Tablas |
|---|---|
| Noticias & Tendencias | news_items, news_interactions |
| Contenido Generado | contents |
| Gestion de Equipos | team_members, team_invitations |
| Roles & Seguridad | user_roles, user_bans, admin_audit_logs |
| IA & Cuotas | ai_usage_logs, user_quotas |
| Facturacion | plans, credit_packs, subscriptions, payments, credit_purchases |
| Configuracion | app_settings |

Total: **15 tablas fisicas** + 1 vista calculada (user_topic_scores)

## Ver el diagrama completo

Abre el PDF generado:

```
tier_database/diagrama_base_datos.pdf
```

Para regenerarlo:
```bash
python tier_database/generate_pdf.py
```
