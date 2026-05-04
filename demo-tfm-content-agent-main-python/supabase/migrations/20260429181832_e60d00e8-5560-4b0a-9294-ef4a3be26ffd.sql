REVOKE EXECUTE ON FUNCTION public.is_user_banned(uuid) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.get_today_usage(uuid, text) FROM anon, authenticated;

DROP POLICY IF EXISTS "Service inserts usage" ON public.ai_usage_logs;
-- Inserts will be performed by edge functions using service role, which bypasses RLS.
-- No INSERT policy means non-service clients cannot insert.