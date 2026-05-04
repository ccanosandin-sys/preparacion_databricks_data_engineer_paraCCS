# Content Agent - Versión Python

Una plataforma SaaS completa para generación de contenido con IA, construida con FastAPI, Supabase y Google Gemini.

## Características

- **Generación de Contenido con IA**: Crea posts, threads, carruseles y videos cortos usando Google Gemini
- **Autenticación y Autorización**: Sistema completo de login/registro con Supabase Auth
- **Panel de Administración**: Gestión de usuarios, analytics y finanzas
- **Gestión de Equipo**: Invitaciones y roles de equipo
- **Analytics**: Métricas de uso y rendimiento
- **Librería de Contenido**: Almacenamiento y gestión de contenido generado
- **Insights**: Análisis predictivo y tendencias
- **Configuración de Marca**: Personalización del tono y estilo de contenido

## Tecnologías

- **Backend**: FastAPI (Python)
- **Base de Datos**: Supabase (PostgreSQL)
- **Autenticación**: Supabase Auth
- **IA**: Google Gemini API
- **Frontend**: Jinja2 templates + Tailwind CSS + Vanilla JavaScript
- **Despliegue**: Uvicorn

## Instalación

1. Clona el repositorio:
```bash
git clone <url-del-repo>
cd demo-tfm-content-agent-main-python
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura las variables de entorno:
Copia `.env.example` a `.env` y configura:
```bash
SUPABASE_URL=tu-supabase-url
SUPABASE_ANON_KEY=tu-anon-key
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key
GEMINI_API_KEY=tu-gemini-api-key
SECRET_KEY=tu-clave-secreta
```

4. Ejecuta la aplicación:
```bash
python main.py
```

La aplicación estará disponible en `http://localhost:8000`

## Estructura del Proyecto

```
├── main.py                 # Punto de entrada de FastAPI
├── app/
│   ├── __init__.py
│   ├── config.py           # Configuración de la aplicación
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py         # Rutas de autenticación
│   │   ├── pages.py        # Rutas de páginas HTML
│   │   └── api/            # APIs REST
│   │       ├── content.py
│   │       ├── news.py
│   │       ├── library.py
│   │       ├── analytics.py
│   │       ├── insights.py
│   │       ├── team.py
│   │       └── admin.py
│   └── services/           # Servicios de negocio
│       ├── __init__.py
│       ├── supabase_client.py
│       ├── ai_service.py
│       ├── news_service.py
│       └── quota_service.py
├── templates/              # Plantillas Jinja2
│   ├── base.html
│   ├── index.html
│   ├── auth.html
│   └── ...
├── static/                 # Archivos estáticos
│   ├── css/
│   └── js/
└── requirements.txt        # Dependencias Python
```

## APIs Principales

### Autenticación
- `POST /auth/login` - Iniciar sesión
- `POST /auth/register` - Registrarse
- `POST /auth/logout` - Cerrar sesión

### Contenido
- `POST /api/content/generate` - Generar contenido
- `GET /api/content/history` - Historial de contenido

### Librería
- `GET /api/library` - Listar contenido guardado
- `POST /api/library/save` - Guardar contenido

### Analytics
- `GET /api/analytics/usage` - Estadísticas de uso
- `GET /api/analytics/content` - Analytics de contenido

### Admin
- `GET /api/admin/users` - Gestión de usuarios
- `GET /api/admin/finance` - Informes financieros

## Desarrollo

Para desarrollo local:
```bash
pip install -r requirements.txt
python main.py
```

La aplicación se recarga automáticamente con cambios.

## Despliegue

La aplicación está preparada para despliegue en cualquier plataforma que soporte Python/FastAPI:

- **Railway**
- **Render**
- **Heroku**
- **Vercel** (con adaptador)
- **AWS Lambda** (con Mangum)

## Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT.
bun run lint      # ESLint
```

## Estructura

```
src/
  components/      # UI compartida (shadcn + propios)
  pages/           # rutas (Dashboard, Create, Library, Analytics, Insights, Brand, Team, Admin, …)
  hooks/           # useAuth, useIsAdmin, etc.
  integrations/    # supabase/, lovable/
  layouts/         # AppLayout
supabase/
  functions/       # Edge Functions (Deno)
  migrations/      # SQL versionadas
plan inicial.md    # plan funcional y técnico del MVP
.lovable/plan.md   # plan que mantiene Lovable
```

## Equipo

Proyecto Fin de Máster, 4 personas. Para colaborar:

1. Clona el repo y crea una rama (`git checkout -b feat/tu-feature`).
2. Cada uno con su `.env` local — **nunca commitearlo**.
3. PRs a `main` con descripción y screenshots si tocan UI.

## Notas de seguridad

- El `.env` está en `.gitignore`. La `anon key` de Supabase es pública por diseño (se incluye en el bundle), pero la seguridad real depende de tener **RLS** activada en todas las tablas.
- `SUPABASE_SERVICE_ROLE_KEY` y `LOVABLE_API_KEY` viven SOLO en los secrets del dashboard de Supabase, nunca en el repo ni en el frontend.
