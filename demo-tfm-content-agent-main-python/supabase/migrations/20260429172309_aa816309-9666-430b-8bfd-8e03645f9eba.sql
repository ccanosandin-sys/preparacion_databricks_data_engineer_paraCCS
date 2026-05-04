
-- Enum de roles de equipo
CREATE TYPE public.team_role AS ENUM ('owner', 'admin', 'editor', 'viewer');

-- Enum de estado de invitaciones
CREATE TYPE public.invitation_status AS ENUM ('pending', 'accepted', 'revoked', 'expired');

-- Enum de estado de contenidos
CREATE TYPE public.content_status AS ENUM ('draft', 'published', 'discarded');

-- ============================================================
-- TEAM MEMBERS
-- ============================================================
CREATE TABLE public.team_members (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  owner_id UUID NOT NULL,           -- dueño del workspace
  member_id UUID NOT NULL,          -- miembro real (auth.users.id)
  role public.team_role NOT NULL DEFAULT 'editor',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, member_id)
);

ALTER TABLE public.team_members ENABLE ROW LEVEL SECURITY;

-- Función helper para evitar recursión
CREATE OR REPLACE FUNCTION public.is_team_member(_owner UUID, _user UUID)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT _owner = _user
      OR EXISTS (
        SELECT 1 FROM public.team_members
        WHERE owner_id = _owner AND member_id = _user
      )
$$;

CREATE POLICY "Owner manages members"
ON public.team_members FOR ALL
USING (auth.uid() = owner_id)
WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Member sees own row"
ON public.team_members FOR SELECT
USING (auth.uid() = member_id);

-- ============================================================
-- TEAM INVITATIONS
-- ============================================================
CREATE TABLE public.team_invitations (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  owner_id UUID NOT NULL,
  email TEXT NOT NULL,
  role public.team_role NOT NULL DEFAULT 'editor',
  status public.invitation_status NOT NULL DEFAULT 'pending',
  token TEXT NOT NULL DEFAULT encode(gen_random_bytes(24), 'hex'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '7 days')
);

CREATE UNIQUE INDEX team_invitations_owner_email_pending_idx
  ON public.team_invitations (owner_id, lower(email))
  WHERE status = 'pending';

ALTER TABLE public.team_invitations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Owner manages invitations"
ON public.team_invitations FOR ALL
USING (auth.uid() = owner_id)
WITH CHECK (auth.uid() = owner_id);

-- ============================================================
-- CONTENTS (borradores, publicados, descartados)
-- ============================================================
CREATE TABLE public.contents (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  format TEXT NOT NULL DEFAULT 'post',
  topic TEXT,
  tone TEXT,
  status public.content_status NOT NULL DEFAULT 'draft',
  source_news_id UUID REFERENCES public.news_items(id) ON DELETE SET NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX contents_user_status_idx ON public.contents (user_id, status, updated_at DESC);

ALTER TABLE public.contents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own contents"
ON public.contents FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users insert own contents"
ON public.contents FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own contents"
ON public.contents FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users delete own contents"
ON public.contents FOR DELETE
USING (auth.uid() = user_id);

CREATE POLICY "Admins view all contents"
ON public.contents FOR SELECT
USING (public.has_role(auth.uid(), 'admin'));

-- Trigger updated_at reutilizando función estándar
CREATE OR REPLACE FUNCTION public.touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER contents_touch_updated_at
BEFORE UPDATE ON public.contents
FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- ============================================================
-- VISTA DE SCORING POR TOPIC PARA RECOMENDACIONES
-- ============================================================
-- Pondera positivo "saved" y "used", negativo "dismissed".
CREATE OR REPLACE VIEW public.user_topic_scores
WITH (security_invoker = on) AS
SELECT
  ni.user_id,
  COALESCE(n.topic, 'otros') AS topic,
  SUM(
    CASE ni.interaction
      WHEN 'saved'     THEN 2
      WHEN 'used'      THEN 3
      WHEN 'dismissed' THEN -1
      ELSE 0
    END
  )::INT AS score,
  COUNT(*)::INT AS interactions
FROM public.news_interactions ni
JOIN public.news_items n ON n.id = ni.news_item_id
GROUP BY ni.user_id, COALESCE(n.topic, 'otros');
