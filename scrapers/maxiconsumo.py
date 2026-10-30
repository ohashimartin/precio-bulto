"""Recolector de precios de Maxiconsumo.

Lee las páginas de categorías públicas (permitidas por su robots.txt),
con una pausa entre pedidos para no cargar su servidor.
Guarda el resultado en data/raw/maxiconsumo.json
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.maxiconsumo.com"
SUCURSAL = "sucursal_moreno"  # precios públicos sin iniciar sesión
PAUSA_SEG = 2.0
HEADERS = {"User-Agent": "ComparadorMayoristas/0.1 (proyecto personal; contacto en el repo)"}

# Canasta inicial: categorías con productos que la gente compra por cantidad
CATEGORIAS = {
    "Arroz": "almacen/arroz",
    "Fideos": "almacen/pastas-secas/fideos",
    "Aceites": "almacen/aceites-y-vinagres/aceites",
    "Harina": "almacen/harinas-y-premezclas/harinas-de-trigo",
    "Azúcar": "almacen/endulzantes/azucar",
    "Yerba": "almacen/infusiones/yerbas",
    "Café": "almacen/infusiones/cafe-y-maltas",
    "Puré de tomate": "almacen/tomates/pure-de-tomate",
    "Leche larga vida": "almacen/leche-larga-vida",
    "Mayonesa": "almacen/aderezos-y-condimentos/mayonesas",
    "Galletitas dulces": "almacen/galletitas/galletitas-dulces",
    "Gaseosas": "bebidas/gaseosas",
    "Detergente": "limpieza/cocina/detergentes-y-lavavajillas",
    "Lavandina": "limpieza/pisos-y-superficies/lavandinas",
    "Papel higiénico": "limpieza/ba-o/papel-higienico",
    "Rollos de cocina": "limpieza/cocina/rollos-de-cocina",
    "Jabón para ropa": "limpieza/ropa/jabones-liquidos",
}


def precio(texto):
    """'$ 1.149,88' -> 1149.88"""
    t = re.sub(r"[^\d,]", "", texto or "")
    return float(t.replace(",", ".")) if t else None


def unidades_por_bulto(item):
    """La mayor 'presentación' con producto asociado = unidades del bulto."""
    sc = item.find("script", string=re.compile("jsonConfig"))
    if not sc:
        return None
    try:
        d = json.loads(sc.string)
        cfg = list(d.values())[0]["Magento_Swatches/js/swatch-renderer"]["jsonConfig"]
        opciones = [
            int(o["label"])
            for attr in cfg["attributes"].values()
            for o in attr["options"]
            if o["products"] and o["label"].isdigit()
        ]
        return max(opciones) if opciones else None
    except (ValueError, KeyError, IndexError):
        return None


def leer_item(item, categoria):
    link = item.select_one("a.product-item-link")
    if not link:
        return None
    sku_el = item.select_one(".product-sku")
    stock_el = item.select_one(".stock-status")
    p_bulto = p_bulto_sin_iva = p_unidad = None
    for cont in item.select(".price-container"):
        label = cont.select_one(".price-label")
        label = label.get_text(strip=True) if label else ""
        precios = [precio(p.get_text()) for p in cont.select(".price")]
        if label.startswith("Precio unitario por bulto"):
            p_bulto = precios[0] if precios else None
            p_bulto_sin_iva = precios[1] if len(precios) > 1 else None
        elif label == "Precio unitario":
            p_unidad = precios[0] if precios else None
    if p_unidad is None and p_bulto is None:
        return None  # productos sin precio visible ("disponibilidad crítica")
    return {
        "cadena": "Maxiconsumo",
        "sucursal": "Moreno",
        "categoria": categoria,
        "nombre": link.get_text(strip=True),
        "sku": re.sub(r"\D", "", sku_el.get_text()) if sku_el else None,
        "precio_unidad": p_unidad,
        "precio_bulto_por_unidad": p_bulto,
        "precio_bulto_sin_iva": p_bulto_sin_iva,
        "unidades_por_bulto": unidades_por_bulto(item),
        "condicion": None,
        "stock": stock_el.get_text(strip=True) if stock_el else None,
        "url": link["href"],
    }


def recolectar():
    sesion = requests.Session()
    sesion.headers.update(HEADERS)
    productos = []
    for categoria, ruta in CATEGORIAS.items():
        pagina = 1
        while True:
            url = f"{BASE}/{SUCURSAL}/{ruta}.html?p={pagina}"
            r = sesion.get(url, timeout=30)
            if r.status_code != 200:
                print(f"  ! {categoria} página {pagina}: HTTP {r.status_code}", file=sys.stderr)
                break
            sopa = BeautifulSoup(r.text, "html.parser")
            items = sopa.select("li.product-item")
            nuevos = [p for p in (leer_item(i, categoria) for i in items) if p]
            productos.extend(nuevos)
            total = sopa.select_one(".toolbar-amount")
            total_txt = total.get_text(" ", strip=True) if total else ""
            print(f"  {categoria} p{pagina}: {len(nuevos)} productos ({total_txt})")
            m = re.search(r"(\d+)\s*-\s*(\d+)\s*de\s*(\d+)", total_txt)
            time.sleep(PAUSA_SEG)
            # los productos sin stock (sin precio) vienen al final: si una página
            # no trae ninguno con precio, las siguientes tampoco
            if not m or int(m.group(2)) >= int(m.group(3)) or not nuevos:
                break
            pagina += 1
    # quitar duplicados (un producto puede aparecer en dos páginas)
    unicos = {p["sku"] or p["url"]: p for p in productos}
    return list(unicos.values())


if __name__ == "__main__":
    salida = Path(__file__).resolve().parent.parent / "data" / "raw" / "maxiconsumo.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    datos = recolectar()
    json.dump(
        {"fuente": BASE, "fecha": datetime.now(timezone.utc).isoformat(), "productos": datos},
        open(salida, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"Listo: {len(datos)} productos -> {salida}")
