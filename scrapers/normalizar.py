"""Une los datos de todas las cadenas en un formato común.

1. Lee data/raw/*.json
2. Saca tamaño y unidad del nombre ("ARROZ X 1 KG" -> 1000 g)
3. Calcula precio por kg / litro / unidad
4. Empareja el mismo producto entre cadenas (mismo tamaño + nombre parecido)
5. Escribe data/precios.json, que es lo que lee la web
"""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

RAIZ = Path(__file__).resolve().parent.parent
MAX_DIAS = 7  # datos más viejos que esto no se publican
UMBRAL_ORDEN = 65  # 0-100: parecido mínimo del nombre completo

CATEGORIA_POR_PALABRA = [
    ("Yerba", ["yerba", "mate cocido"]), ("Fideos", ["fideo", "ramen", "tallarin"]),
    ("Arroz", ["arroz"]), ("Aceites", ["aceite"]), ("Harina", ["harina"]),
    ("Azúcar", ["azucar"]), ("Café", ["cafe"]), ("Puré de tomate", ["pure de tomate", "pure "]),
    ("Leche larga vida", ["leche"]), ("Mayonesa", ["mayonesa"]),
    ("Galletitas dulces", ["galletita", "bizcochuelo"]), ("Gaseosas", ["coca cola", "gaseosa", "pepsi"]),
    ("Cervezas", ["cerveza"]), ("Detergente", ["detergente", "lavavajilla"]),
    ("Lavandina", ["lavandina"]), ("Papel higiénico", ["papel higienico"]),
    ("Rollos de cocina", ["rollo de cocina", "rollo cocina"]), ("Jabón para ropa", ["jabon liquido", "jabon en polvo", "jabon en pan"]),
]

PALABRAS_VACIAS = {"x", "de", "con", "el", "la", "los", "las", "en", "y", "un", "gr", "grs", "g", "kg", "lt", "l",
                   "cc", "ml", "mt", "un", "unidades", "panos", "d", "p", "doypack", "botella", "pet", "brik", "tetra",
                   "gaseosa", "original"}


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def limpiar(nombre):
    t = sin_acentos(nombre.lower())
    t = t.replace("acite", "aceite")  # errores de tipeo frecuentes
    return re.sub(r"\s+", " ", t).strip()


def tamano(nombre):
    """Devuelve (cantidad_total, unidad_base) con unidad_base en g, ml, un o m."""
    t = limpiar(nombre).replace(",", ".")
    if "combo" in t or "+" in t:
        return None, None  # combos de varios productos: no tiene sentido el precio por kg/litro
    # multipacks tipo "3 x 40 panos", "4x30 mt", "3 un x 120 grs"
    m = re.search(r"(\d+)\s*(?:un\s*)?x\s*(\d+(?:\.\d+)?)\s*(panos|mt|grs?|g|ml|cc)\b", t)
    if m:
        n, c, u = int(m.group(1)), float(m.group(2)), m.group(3)
        base = {"panos": "un", "mt": "m", "gr": "g", "grs": "g", "g": "g", "ml": "ml", "cc": "ml"}[u]
        return n * c, base
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(kg|kgs|grs?|g|lts?|l|ml|cc|cm3|panos|un|mt)\b", t)
    if not m:
        return None, None
    c, u = m[-1]
    c = float(c)
    if u in ("kg", "kgs"):
        # error de carga frecuente: "500 KG" cuando son 500 gramos
        return (c, "g") if c >= 50 else (c * 1000, "g")
    if u in ("gr", "grs", "g"):
        return c, "g"
    if u in ("lt", "lts", "l"):
        return c * 1000, "ml"
    if u in ("ml", "cc", "cm3"):
        return c, "ml"
    if u == "mt":
        return c, "m"
    return c, "un"


def precio_por_medida(precio, cantidad, unidad):
    """Precio por kg, por litro, por unidad o por metro."""
    if not precio or not cantidad:
        return None, None
    if unidad == "g":
        return round(precio / cantidad * 1000, 2), "kg"
    if unidad == "ml":
        return round(precio / cantidad * 1000, 2), "litro"
    if unidad == "m":
        return round(precio / cantidad * 10, 2), "10 m"
    return round(precio / cantidad, 2), "unidad"


def categoria_de(nombre, actual):
    if actual:
        return actual
    t = limpiar(nombre)
    for cat, claves in CATEGORIA_POR_PALABRA:
        if any(k in t for k in claves):
            return cat
    return "Otros"


def tokens_clave(nombre):
    t = re.sub(r"\d+(?:[.,]\d+)?", " ", limpiar(nombre))
    t = re.sub(r"[^a-z ]", " ", t)
    return " ".join(w for w in t.split() if w not in PALABRAS_VACIAS)


def main():
    productos = []
    fechas = {}
    for archivo in sorted((RAIZ / "data" / "raw").glob("*.json")):
        d = json.load(open(archivo, encoding="utf-8"))
        antiguedad = datetime.now(timezone.utc) - datetime.fromisoformat(d["fecha"])
        if antiguedad.days > MAX_DIAS:
            print(f"  ! {archivo.name}: datos de hace {antiguedad.days} días, no se muestran")
            continue
        for p in d["productos"]:
            cant, uni = tamano(p["nombre"])
            mejor = p["precio_bulto_por_unidad"] or p["precio_unidad"]
            p["categoria"] = categoria_de(p["nombre"], p["categoria"])
            p["cantidad"], p["unidad_base"] = cant, uni
            p["precio_medida_unidad"], p["medida"] = precio_por_medida(p["precio_unidad"], cant, uni)
            p["precio_medida_bulto"], _ = precio_por_medida(p["precio_bulto_por_unidad"], cant, uni)
            p["precio_mejor"] = mejor
            p["clave"] = tokens_clave(p["nombre"])
            productos.append(p)
            fechas[p["cadena"]] = d["fecha"]

    # Emparejar entre cadenas. Regla estricta, pensada para no mezclar productos distintos:
    #  - mismo tamaño y misma unidad
    #  - todas las palabras del nombre más corto están en el otro (token_set = 100)
    #  - los nombres completos se parecen lo suficiente (token_sort >= UMBRAL_ORDEN)
    #  - cada producto se queda con su ÚNICO mejor candidato en la otra cadena
    # Además, data/equivalencias.json permite forzar o prohibir pares a mano.
    equiv_path = RAIZ / "data" / "equivalencias.json"
    equiv = json.load(open(equiv_path, encoding="utf-8")) if equiv_path.exists() else {"forzar": [], "prohibir": []}
    def par(a, b):
        return tuple(sorted([f"{a['cadena']}:{a['sku']}", f"{b['cadena']}:{b['sku']}"]))
    forzados = {tuple(sorted(x)) for x in equiv.get("forzar", [])}
    prohibidos = {tuple(sorted(x)) for x in equiv.get("prohibir", [])}

    for i, p in enumerate(productos):
        p["grupo"] = i
    cadenas = sorted({p["cadena"] for p in productos})
    usados = set()
    for ci, ca in enumerate(cadenas):
        for cb in cadenas[ci + 1:]:
            A = [p for p in productos if p["cadena"] == ca]
            B = [p for p in productos if p["cadena"] == cb]
            candidatos = []
            for a in A:
                for b in B:
                    k = par(a, b)
                    if k in prohibidos:
                        continue
                    if k in forzados:
                        candidatos.append((1000, a, b))
                        continue
                    if not a["cantidad"] or a["cantidad"] != b["cantidad"] or a["unidad_base"] != b["unidad_base"]:
                        continue
                    if fuzz.token_set_ratio(a["clave"], b["clave"]) < 100:
                        continue
                    orden = fuzz.token_sort_ratio(a["clave"], b["clave"])
                    if orden >= UMBRAL_ORDEN:
                        candidatos.append((orden, a, b))
            for puntaje, a, b in sorted(candidatos, key=lambda c: -c[0]):
                if id(a) in usados or id(b) in usados:
                    continue
                usados.update({id(a), id(b)})
                b["grupo"] = a["grupo"]
                a["confianza"] = b["confianza"] = "manual" if puntaje == 1000 else round(puntaje)

    salida = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "fechas_por_cadena": fechas,
        "productos": productos,
    }
    json.dump(salida, open(RAIZ / "data" / "precios.json", "w", encoding="utf-8"), ensure_ascii=False)
    emparejados = {p["grupo"] for p in productos if sum(q["grupo"] == p["grupo"] for q in productos) > 1}
    print(f"{len(productos)} productos, {len(emparejados)} emparejados entre cadenas")


if __name__ == "__main__":
    main()
