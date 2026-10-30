"""Recolector de las ofertas PÚBLICAS de Yaguar (página de cada sucursal).

Importante: Yaguar tiene una protección anti-robots (Cloudflare) que hoy
bloquea pedidos desde servidores (responde 403). Este script NO intenta
saltear esa protección: si recibe 403, avisa y no guarda nada.
La salida correcta para automatizarlo es pedirle permiso a Yaguar
(o que nos den un archivo/listado de ofertas).

La tienda completa de Yaguar requiere iniciar sesión como comerciante:
no la usamos.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SUCURSALES = {"parque-avellaneda": "Parque Avellaneda"}
HEADERS = {"User-Agent": "ComparadorMayoristas/0.1 (proyecto personal; contacto en el repo)"}
PATRON = re.compile(r"^(.*?) SKU: ([\d, A-Z]+?) (?:\$ ([\d.]+)|(\d+)% Descuento)")


def leer_sucursal(slug, nombre):
    url = f"https://yaguar.com.ar/{slug}/"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 403:
        print(f"  ! Yaguar bloquea el acceso automático (403) en {url}. No se guarda nada.", file=sys.stderr)
        return None
    r.raise_for_status()
    sopa = BeautifulSoup(r.text, "html.parser")
    vistos, productos = set(), []
    for h in sopa.find_all("h4"):
        titulo = h.get_text(strip=True)
        if titulo in vistos:
            continue
        nodo = h.parent
        for _ in range(4):
            if nodo is None:
                break
            texto = re.sub(r"\s+", " ", nodo.get_text(" ")).strip()
            m = PATRON.match(texto) if texto.startswith(titulo) else None
            if m:
                break
            nodo = nodo.parent
        else:
            m = None
        if not m or not m.group(3):
            continue
        vistos.add(titulo)
        sku = m.group(2).strip()
        variantes = "," in sku or "/" in titulo
        productos.append({
            "cadena": "Yaguar", "sucursal": nombre, "categoria": None,
            "nombre": titulo, "sku": sku,
            "precio_unidad": float(m.group(3).replace(".", "")),
            "precio_bulto_por_unidad": None, "precio_bulto_sin_iva": None,
            "unidades_por_bulto": None,
            "condicion": "Oferta de la semana" + (" · varios sabores/variantes" if variantes else ""),
            "stock": None, "url": url,
        })
    return productos


if __name__ == "__main__":
    salida = Path(__file__).resolve().parent.parent / "data" / "raw" / "yaguar.json"
    todos = []
    for slug, nombre in SUCURSALES.items():
        prods = leer_sucursal(slug, nombre)
        if prods is None:
            sys.exit(0)  # se conserva el último archivo bueno
        todos.extend(prods)
    json.dump({"fuente": "https://yaguar.com.ar/", "fecha": datetime.now(timezone.utc).isoformat(),
               "metodo": "pagina publica de ofertas", "productos": todos},
              open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Listo: {len(todos)} ofertas -> {salida}")
