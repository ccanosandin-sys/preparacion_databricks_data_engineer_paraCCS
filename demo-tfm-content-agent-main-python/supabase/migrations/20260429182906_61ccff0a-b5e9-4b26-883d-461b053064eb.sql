-- Plans catalog
CREATE TABLE public.plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  price_monthly_cents INTEGER NOT NULL DEFAULT 0,
  price_yearly_cents INTEGER NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'EUR',
  monthly_credits INTEGER NOT NULL DEFAULT 0,
  monthly_image_credits INTEGER NOT NULL DEFAULT 0,
  features JSONB,
  active BOOLEAN NOT NULL DEFAULT true,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone reads plans" ON public.plans FOR SELECT USING (true);
CREATE POLICY "Admins manage plans" ON public.plans FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER plans_touch BEFORE UPDATE ON public.plans
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

INSERT INTO public.plans (key, name, description, price_monthly_cents, price_yearly_cents, monthly_credits, monthly_image_credits, sort_order, features) VALUES
  ('free', 'Free', 'Para empezar', 0, 0, 30, 10, 0, '["10 contenidos/día","10 imágenes/mes","Soporte comunidad"]'::jsonb),
  ('pro', 'Pro', 'Para creadores activos', 1900, 19000, 500, 200, 1, '["Generaciones ilimitadas","200 imágenes/mes","Exportación HD","Soporte prioritario"]'::jsonb),
  ('business', 'Business', 'Para equipos', 4900, 49000, 2000, 1000, 2, '["Hasta 10 usuarios","1000 imágenes/mes","API access","SLA dedicado"]'::jsonb);

-- Credit packs (one-off top-ups)
CREATE TABLE public.credit_packs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  credits INTEGER NOT NULL,
  image_credits INTEGER NOT NULL DEFAULT 0,
  price_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  active BOOLEAN NOT NULL DEFAULT true,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.credit_packs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone reads packs" ON public.credit_packs FOR SELECT USING (true);
CREATE POLICY "Admins manage packs" ON public.credit_packs FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

INSERT INTO public.credit_packs (key, name, credits, image_credits, price_cents, sort_order) VALUES
  ('starter', 'Starter Pack', 100, 50, 500, 0),
  ('boost',   'Boost Pack',   500, 200, 1900, 1),
  ('mega',    'Mega Pack',    2000, 800, 5900, 2);

-- Subscriptions
CREATE TYPE public.subscription_status AS ENUM ('trialing','active','canceled','past_due','paused');
CREATE TYPE public.billing_interval AS ENUM ('monthly','yearly');

CREATE TABLE public.subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  plan_id UUID NOT NULL REFERENCES public.plans(id),
  status public.subscription_status NOT NULL DEFAULT 'active',
  interval public.billing_interval NOT NULL DEFAULT 'monthly',
  current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
  current_period_end TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 month'),
  canceled_at TIMESTAMPTZ,
  trial_end TIMESTAMPTZ,
  external_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_subs_user ON public.subscriptions(user_id);
CREATE INDEX idx_subs_status ON public.subscriptions(status);
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users view own subs" ON public.subscriptions FOR SELECT
  USING (auth.uid() = user_id);
CREATE POLICY "Admins manage subs" ON public.subscriptions FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER subs_touch BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- Payments
CREATE TYPE public.payment_status AS ENUM ('succeeded','pending','failed','refunded');

CREATE TABLE public.payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  subscription_id UUID REFERENCES public.subscriptions(id) ON DELETE SET NULL,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status public.payment_status NOT NULL DEFAULT 'succeeded',
  reason TEXT NOT NULL DEFAULT 'subscription', -- subscription | credit_pack | manual
  description TEXT,
  external_id TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payments_user_created ON public.payments(user_id, created_at DESC);
CREATE INDEX idx_payments_created ON public.payments(created_at DESC);
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users view own payments" ON public.payments FOR SELECT
  USING (auth.uid() = user_id);
CREATE POLICY "Admins manage payments" ON public.payments FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Credit purchases
CREATE TABLE public.credit_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  pack_id UUID NOT NULL REFERENCES public.credit_packs(id),
  payment_id UUID REFERENCES public.payments(id) ON DELETE SET NULL,
  credits_granted INTEGER NOT NULL,
  image_credits_granted INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_credit_purchases_user ON public.credit_purchases(user_id);
ALTER TABLE public.credit_purchases ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users view own credit purchases" ON public.credit_purchases FOR SELECT
  USING (auth.uid() = user_id);
CREATE POLICY "Admins manage credit purchases" ON public.credit_purchases FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));