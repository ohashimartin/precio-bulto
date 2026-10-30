"""Arma web/index.html metiendo data/precios.json dentro de la plantilla.

Solo se incluyen los campos que la web usa, para que la página sea liviana.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMPOS = ["cadena", "sucursal", "categoria", "nombre", "precio_unidad", "precio_bulto_por_unidad",
          "unidades_por_bulto", "condicion", "precio_medida_unidad", "precio_medida_bulto", "medida",
          "grupo", "url"]

datos = json.load(open(RAIZ / "data" / "precios.json", encoding="utf-8"))
datos["productos"] = [{k: p.get(k) for k in CAMPOS} for p in datos["productos"]]
plantilla = (RAIZ / "web" / "plantilla.html").read_text(encoding="utf-8")
html = plantilla.replace("/*DATOS*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
(RAIZ / "web" / "index.html").write_text(html, encoding="utf-8")
print(f"web/index.html listo ({len(html) // 1024} KB, {len(datos['productos'])} productos)")
