
-- News items cache
CREATE TABLE public.news_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  workspace_id UUID,
  title TEXT NOT NULL,
  summary TEXT,
  source_url TEXT NOT NULL,
  source_name TEXT,
  published_at TIMESTAMPTZ,
  topic TEXT,
  language TEXT DEFAULT 'es',
  raw JSONB,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_news_items_user ON public.news_items(user_id, fetched_at DESC);
CREATE INDEX idx_news_items_workspace ON public.news_items(workspace_id) WHERE workspace_id IS NOT NULL;
CREATE UNIQUE INDEX idx_news_items_dedupe ON public.news_items(user_id, source_url);

ALTER TABLE public.news_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own news" ON public.news_items FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own news" ON public.news_items FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own news" ON public.news_items FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users delete own news" ON public.news_items FOR DELETE USING (auth.uid() = user_id);

-- Interactions (saved / dismissed) — feeds learning loop
CREATE TYPE public.news_interaction_type AS ENUM ('saved', 'dismissed', 'used');

CREATE TABLE public.news_interactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  news_item_id UUID NOT NULL REFERENCES public.news_items(id) ON DELETE CASCADE,
  interaction news_interaction_type NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, news_item_id, interaction)
);

CREATE INDEX idx_news_interactions_user ON public.news_interactions(user_id, created_at DESC);

ALTER TABLE public.news_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own interactions" ON public.news_interactions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own interactions" ON public.news_interactions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own interactions" ON public.news_interactions FOR DELETE USING (auth.uid() = user_id);
