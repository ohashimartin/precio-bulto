# Precio Bulto — comparador de precios mayoristas

Compara precios de supermercados mayoristas de Argentina: precio por unidad,
precio comprando el bulto cerrado y precio por kilo o litro.

## Cómo funciona

```
scrapers/maxiconsumo.py   -> data/raw/maxiconsumo.json   (lee la web pública de Maxiconsumo)
scrapers/yaguar.py        -> data/raw/yaguar.json        (ofertas públicas de Yaguar)
scrapers/normalizar.py    -> data/precios.json           (tamaños, precio por kg, emparejado)
scrapers/construir_web.py -> web/index.html              (la página que ve la gente)
```

Todos los días a las 6:17 (hora Argentina) GitHub corre esos cuatro pasos solo
(archivo `.github/workflows/actualizar.yml`) y publica la web actualizada.

## Fuentes y reglas que respetamos

| Cadena | Qué usamos | Estado |
|---|---|---|
| Maxiconsumo | Páginas de categorías públicas (permitidas en su robots.txt), sucursal Moreno | Funciona |
| Yaguar | Solo la página pública de ofertas de cada sucursal | Su protección anti-robots bloquea servidores. No la salteamos. |
| Vital | — | Los precios requieren iniciar sesión. No se usa. |
| Diarco, Makro, Nini | — | Publican folletos en imagen. Pendiente. |

- Una pausa de 2 segundos entre cada página, una vez por día.
- Nunca usamos secciones que piden iniciar sesión.
- Si los datos de una cadena tienen más de 7 días, no se muestran.

## Corregir emparejados

`data/equivalencias.json` permite decir a mano que dos productos son el mismo
(`forzar`) o que no lo son (`prohibir`), usando `"Cadena:SKU"`.

## Ponerlo en marcha en GitHub (paso a paso)

1. Creá una cuenta gratis en https://github.com
2. Arriba a la derecha: **+ → New repository**. Nombre: `precio-bulto`. Dejalo **Public** y tocá **Create repository**.
3. En el repositorio nuevo: **Add file → Upload files**, arrastrá TODO el contenido de esta carpeta (incluida la carpeta `.github`) y tocá **Commit changes**.
4. **Settings → Pages → Source: GitHub Actions**.
5. **Actions → Actualizar precios → Run workflow**. A los pocos minutos la web queda en
   `https://TU-USUARIO.github.io/precio-bulto/`

## Correrlo en tu compu (opcional)

```
pip install -r requirements.txt
python scrapers/maxiconsumo.py
python scrapers/normalizar.py
python scrapers/construir_web.py
```
Después abrí `web/index.html` con el navegador.
