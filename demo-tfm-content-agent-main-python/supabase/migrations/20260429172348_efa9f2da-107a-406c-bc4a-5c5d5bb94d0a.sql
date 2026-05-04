
REVOKE EXECUTE ON FUNCTION public.is_team_member(UUID, UUID) FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.is_team_member(UUID, UUID) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.has_role(UUID, app_role) FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.has_role(UUID, app_role) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.touch_updated_at() FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.touch_updated_at() TO authenticated;
