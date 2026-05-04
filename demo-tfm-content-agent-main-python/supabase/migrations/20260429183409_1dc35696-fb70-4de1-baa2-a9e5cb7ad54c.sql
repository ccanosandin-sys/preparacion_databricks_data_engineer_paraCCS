
CREATE TABLE public.admin_audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_id uuid NOT NULL,
  admin_email text,
  target_user_id uuid,
  target_user_email text,
  action text NOT NULL,
  payload jsonb,
  result jsonb,
  success boolean NOT NULL DEFAULT true,
  error_message text,
  ip_address text,
  user_agent text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_admin_audit_logs_created_at ON public.admin_audit_logs (created_at DESC);
CREATE INDEX idx_admin_audit_logs_admin_id ON public.admin_audit_logs (admin_id);
CREATE INDEX idx_admin_audit_logs_target_user_id ON public.admin_audit_logs (target_user_id);
CREATE INDEX idx_admin_audit_logs_action ON public.admin_audit_logs (action);

ALTER TABLE public.admin_audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins view audit logs"
  ON public.admin_audit_logs
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins insert audit logs"
  ON public.admin_audit_logs
  FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
