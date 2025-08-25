# app.py
from flask import Flask, request, send_file, jsonify, abort
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from datetime import date, timedelta
import io, os
import random


# ---- Instancia Flask (¡esto es tu 'app' real!) ----
app = Flask(__name__)

# ---- Jinja2 / plantillas ----
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape()
)
env.globals.update(enumerate=enumerate)


# Filtro $ 1.234.567,89
def money_ar(value):
    try:
        n = float(value)
    except:
        return ""
    s = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"
env.filters["money"] = money_ar

EMPRESA = {
    "nombre": "The Gamer Shop",
    "cond_iva": "Responsable Inscripto",
    "cuit": "23-22364802-9",
    "ing_brutos": "0088520-07",
    "inicio_act": "21/10/1992",
    "domicilio": "Carhue 1409, CABA, Argentina",
    "cond_iva_cliente": "Consumidor Final",
}

def render_pdf_from_payload(payload):
    hoy = date.today()
    dias = int(payload.get("meta", {}).get("validez_dias", 7) or 7)
    vto = hoy + timedelta(days=dias)

    # ---- número aleatorio 0..9999 si no viene definido ----
    meta = dict(payload.get("meta") or {})
    numero_actual = str(meta.get("numero") or "").strip()
    if not numero_actual:
        meta["numero"] = f"{random.randint(0, 9999):04d}"  # ej: 0427 (4 dígitos)
    # guardar de vuelta en el payload que se envía a la plantilla
    payload = dict(payload)
    payload["meta"] = meta
    # -------------------------------------------------------

    total_pc = _total_pc(payload)
    lineas   = [_linea_resumen(payload, total_pc), * _lineas_detalle_cero(payload)]

    html_str = env.get_template("presupuesto.html").render(
        payload=payload, empresa=EMPRESA, hoy=hoy, vto=vto,
        lineas=lineas, total_pc=total_pc
    )
    base = os.path.join(app.root_path, "static")
    pdf_bytes = HTML(string=html_str, base_url=base).write_pdf()
    return pdf_bytes



def _total_pc(payload: dict) -> float:
    # usa el total que mandas desde Sheets si viene
    try:
        tf = float((payload.get("resumen") or {}).get("final_transferencia") or 0)
    except:
        tf = 0.0
    if tf > 0:
        return tf
    # si no vino, suma de items
    total = 0.0
    for it in (payload.get("items") or []):
        try:
            cant   = float(it.get("cantidad") or 1)
            precio = float(it.get("precio_unit") or 0)
            dto    = float(it.get("descuento") or 0)
        except:
            cant, precio, dto = 1.0, 0.0, 0.0
        total += cant * precio * (1 - dto/100.0)
    return total

def _linea_resumen(payload: dict, total_pc: float) -> dict:
    return {
        "producto": "Presupuesto de PC  Armada",
        "observacion": (
            "Servicio de Armado y Configuración de PC, "
            "Incluye la instalación del Sistema Operativo Windows 11/10 Pro/Home"
        ),
        "cantidad": 1,
        "precio_unit": float(total_pc),
        "descuento": 0,
    }

def _lineas_detalle_cero(payload: dict) -> list[dict]:
    out = []
    for it in (payload.get("items") or []):
        nombre = (it.get("producto") or "").strip()
        if not nombre:
            continue
        out.append({
            "producto": nombre,
            "observacion": "",   # sin texto gris
            "cantidad": 1,
            "precio_unit": 0,    # << precio 0
            "descuento": 0,
        })
    return out

# ----------- RUTAS -----------
@app.get("/health")
def health():
    return jsonify(ok=True)

@app.post("/presupuesto")
def presupuesto():
    data = request.get_json(force=True) or {}
    pdf_bytes = render_pdf_from_payload(data)
    nombre = (data.get("meta", {}) or {}).get("titulo") or "Presupuesto"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,               # True si querés forzar descarga
        download_name=f"{nombre}.pdf"
    )

# ---- Main guard: arranque del servidor ----
if __name__ == "__main__":
    print("Starting Flask on http://127.0.0.1:8000 ...")
    app.run(host="127.0.0.1", port=8000, debug=True)
