-- AI usage logs
CREATE TABLE public.ai_usage_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  function_name TEXT NOT NULL,
  model TEXT,
  kind TEXT NOT NULL DEFAULT 'content', -- content | image
  tokens_in INTEGER DEFAULT 0,
  tokens_out INTEGER DEFAULT 0,
  images_count INTEGER DEFAULT 0,
  estimated_cost_usd NUMERIC(10,5) DEFAULT 0,
  success BOOLEAN NOT NULL DEFAULT true,
  error_message TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_usage_logs_user_created ON public.ai_usage_logs(user_id, created_at DESC);
CREATE INDEX idx_ai_usage_logs_created ON public.ai_usage_logs(created_at DESC);
ALTER TABLE public.ai_usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own usage" ON public.ai_usage_logs
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Admins view all usage" ON public.ai_usage_logs
  FOR SELECT USING (public.has_role(auth.uid(), 'admin'));
CREATE POLICY "Service inserts usage" ON public.ai_usage_logs
  FOR INSERT WITH CHECK (true);

-- User quotas
CREATE TABLE public.user_quotas (
  user_id UUID PRIMARY KEY,
  daily_content_limit INTEGER NOT NULL DEFAULT 50,
  daily_image_limit INTEGER NOT NULL DEFAULT 30,
  monthly_content_limit INTEGER NOT NULL DEFAULT 1000,
  monthly_image_limit INTEGER NOT NULL DEFAULT 500,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.user_quotas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own quota" ON public.user_quotas
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Admins manage quotas" ON public.user_quotas
  FOR ALL USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE TRIGGER user_quotas_touch
  BEFORE UPDATE ON public.user_quotas
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- User bans
CREATE TABLE public.user_bans (
  user_id UUID PRIMARY KEY,
  reason TEXT,
  banned_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.user_bans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own ban" ON public.user_bans
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Admins manage bans" ON public.user_bans
  FOR ALL USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- App settings (global)
CREATE TABLE public.app_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by UUID
);
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone reads settings" ON public.app_settings
  FOR SELECT USING (true);
CREATE POLICY "Admins write settings" ON public.app_settings
  FOR ALL USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

INSERT INTO public.app_settings (key, value) VALUES
  ('maintenance_mode', '{"enabled": false}'::jsonb),
  ('global_banner', '{"enabled": false, "message": "", "variant": "info"}'::jsonb),
  ('default_models', '{"content": "google/gemini-2.5-flash", "image": "google/gemini-2.5-flash-image-preview"}'::jsonb);

-- Helpers
CREATE OR REPLACE FUNCTION public.is_user_banned(_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS(SELECT 1 FROM public.user_bans WHERE user_id = _user_id)
$$;

CREATE OR REPLACE FUNCTION public.get_today_usage(_user_id UUID, _kind TEXT)
RETURNS INTEGER
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT COALESCE(SUM(CASE WHEN _kind='image' THEN images_count ELSE 1 END), 0)::int
  FROM public.ai_usage_logs
  WHERE user_id = _user_id
    AND kind = _kind
    AND success = true
    AND created_at >= date_trunc('day', now());
$$;