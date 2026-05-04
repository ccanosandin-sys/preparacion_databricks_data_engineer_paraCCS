-- Hacemos el bucket privado para evitar listing, pero servimos via signed URL o desde el frontend con auth.
-- Para mantener acceso fácil sin signed URLs, dejamos el bucket público pero en realidad
-- el problema del linter es la policy que permite SELECT sin filtros. La solución correcta:
-- mantener el bucket privado y usar signed URLs (más seguro) O
-- aceptar el riesgo (las URLs no son enumerables sin permisos de listado de objetos).
-- Optamos por: bucket privado + lectura solo para el dueño + signed URLs para reproducir.

UPDATE storage.buckets SET public = false WHERE id = 'short-assets';

-- Reemplazamos la policy de lectura pública por una que solo permite al dueño
DROP POLICY IF EXISTS "Public read short-assets" ON storage.objects;

CREATE POLICY "Users read own short-assets"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'short-assets'
  AND auth.uid()::text = (storage.foldername(name))[1]
);