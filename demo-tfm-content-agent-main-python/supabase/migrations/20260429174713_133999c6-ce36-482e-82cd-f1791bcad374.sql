-- Bucket público para imágenes B-roll de los shorts
INSERT INTO storage.buckets (id, name, public)
VALUES ('short-assets', 'short-assets', true)
ON CONFLICT (id) DO NOTHING;

-- Lectura pública (necesaria para que el player las muestre)
CREATE POLICY "Public read short-assets"
ON storage.objects FOR SELECT
USING (bucket_id = 'short-assets');

-- Solo usuarios autenticados pueden subir a su propia carpeta
CREATE POLICY "Users upload own short-assets"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'short-assets'
  AND auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users update own short-assets"
ON storage.objects FOR UPDATE
TO authenticated
USING (
  bucket_id = 'short-assets'
  AND auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users delete own short-assets"
ON storage.objects FOR DELETE
TO authenticated
USING (
  bucket_id = 'short-assets'
  AND auth.uid()::text = (storage.foldername(name))[1]
);