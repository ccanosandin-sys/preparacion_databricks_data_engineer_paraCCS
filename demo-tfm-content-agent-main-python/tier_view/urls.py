from django.urls import path
from tier_view import views, auth_views
from tier_view.api import content, news, library, analytics, insights, team, admin as admin_api, user

urlpatterns = [
    # ── Páginas HTML ──────────────────────────────────────────────
    path("landing", views.landing, name="landing"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("app/create", views.create_page, name="create"),
    path("app/content", views.library_page, name="library"),
    path("app/trends", views.trends_page, name="trends"),
    path("app/analytics", views.analytics_page, name="analytics"),
    path("app/insights", views.insights_page, name="insights"),
    path("app/brand", views.brand_page, name="brand"),
    path("app/team", views.team_page, name="team"),
    path("settings", views.settings_page, name="settings"),
    path("admin", views.admin_page, name="admin"),

    # ── Auth ──────────────────────────────────────────────────────
    path("auth/login", auth_views.login_page, name="login"),
    path("auth/login/", auth_views.login_post, name="login_post"),
    path("auth/signup", auth_views.signup_page, name="signup"),
    path("auth/signup/", auth_views.signup_post, name="signup_post"),
    path("auth/logout", auth_views.logout, name="logout"),

    # ── API: Contenido ────────────────────────────────────────────
    path("api/generate-content", content.generate_content, name="api_generate_content"),
    path("api/contents", content.save_content, name="api_save_content"),

    # ── API: Biblioteca ───────────────────────────────────────────
    path("api/contents/list", library.list_contents, name="api_list_contents"),
    path("api/contents/<str:content_id>", library.get_content, name="api_get_content"),
    path("api/contents/<str:content_id>/update", library.update_content, name="api_update_content"),
    path("api/contents/<str:content_id>/delete", library.delete_content, name="api_delete_content"),
    path("api/contents/<str:content_id>/duplicate", library.duplicate_content, name="api_duplicate_content"),
    path("api/news-items", library.list_saved_news, name="api_saved_news"),

    # ── API: Noticias ─────────────────────────────────────────────
    path("api/fetch-news", news.fetch_news, name="api_fetch_news"),
    path("api/rank-news", news.rank_news_view, name="api_rank_news"),
    path("api/news-interaction", news.news_interaction, name="api_news_interaction"),

    # ── API: Analytics / Insights ─────────────────────────────────
    path("api/analytics", analytics.get_analytics, name="api_analytics"),
    path("api/generate-insights", insights.generate_insights, name="api_insights"),

    # ── API: Equipo ───────────────────────────────────────────────
    path("api/team/members", team.list_members, name="api_team_members"),
    path("api/team/invitations", team.list_invitations, name="api_team_invitations"),
    path("api/team/invite", team.invite_member, name="api_team_invite"),
    path("api/team/invitations/<str:invitation_id>/revoke", team.revoke_invitation, name="api_revoke_invitation"),
    path("api/team/members/<str:member_id>/update", team.update_member, name="api_update_member"),
    path("api/team/members/<str:member_id>/remove", team.remove_member, name="api_remove_member"),

    # ── API: Admin ────────────────────────────────────────────────
    path("api/overview", admin_api.overview, name="api_admin_overview"),
    path("api/admin/users", admin_api.list_users, name="api_admin_users"),
    path("api/admin/contents", admin_api.list_contents, name="api_admin_contents"),
    path("api/admin/ai-logs", admin_api.ai_logs, name="api_admin_ai_logs"),
    path("api/admin/audit-logs", admin_api.audit_logs, name="api_admin_audit_logs"),
    path("api/admin/settings", admin_api.get_settings, name="api_admin_settings"),
    path("api/admin/settings/update", admin_api.update_setting, name="api_admin_update_setting"),
    path("api/admin/ban-user", admin_api.ban_user, name="api_admin_ban"),
    path("api/admin/unban-user", admin_api.unban_user, name="api_admin_unban"),
    path("api/admin/set-admin", admin_api.set_admin, name="api_admin_set_admin"),
    path("api/admin/set-quota", admin_api.set_quota, name="api_admin_set_quota"),
    path("api/admin/contents/<str:content_id>/delete", admin_api.admin_delete_content, name="api_admin_delete_content"),

    # ── API: Usuario ──────────────────────────────────────────────
    path("api/user/profile", user.get_profile, name="api_user_profile"),
    path("api/user/profile/update", user.update_profile, name="api_update_profile"),
    path("api/user/preferences", user.update_preferences, name="api_update_preferences"),
]

handler404 = "tier_view.views.not_found_page"
