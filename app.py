import io
import os
import random
import logging
import inspect
from datetime import date, timedelta

from flask import Flask, request, send_file
from weasyprint import HTML

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────
def _to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _total_pc(payload: dict) -> float:
    total = 0.0
    for it in (payload.get("items") or []):
        precio = (
            it.get("precio_fin") or it.get("precioFinal")
            or it.get("precio_unit") or it.get("precioUnit")
            or it.get("precio") or 0
        )
        cant = _to_float(it.get("cantidad") or 1)
        dto = _to_float(it.get("descuento") or 0)
        total += _to_float(precio) * cant * (1 - dto / 100.0)
    return total


# 🔥 NUEVO: todos los cálculos
def _calcular_totales(payload: dict) -> dict:
    total_efv = _total_pc(payload)

    # Precio lista
    total_lista = total_efv * 1.15

    # BBVA
    total_bbva = total_efv * 1.13
    bbva_3 = total_bbva / 3
    bbva_6 = total_bbva / 6

    # Otros bancos
    total_cuotas_base = total_efv * 1.13

    cuotas_3_total = total_cuotas_base * 1.105
    cuotas_3 = cuotas_3_total / 3

    cuotas_6_total = total_cuotas_base * 1.215
    cuotas_6 = cuotas_6_total / 6

    cuotas_12_total = total_cuotas_base * 1.94
    cuotas_12 = cuotas_12_total / 12

    return {
        "total_PC_efv": total_efv,
        "total_PC": total_lista,
        "total_PC_BBVA": total_bbva,
        "bbva_3": bbva_3,
        "bbva_6": bbva_6,
        "total_PC_Cuotas": total_cuotas_base,
        "cuotas_3": cuotas_3,
        "cuotas_6": cuotas_6,
        "cuotas_12": cuotas_12,
    }


def _linea_resumen(total_pc: float) -> dict:
    return {
        "producto": "Presupuesto de PC Armada: The Gamer Shop",
        "observacion": (
            "Servicio de Armado y Configuración de PC,\n"
            "Incluye la instalación del Sistema Operativo Windows 11/10 Pro/Home"
        ),
        "cantidad": 1,
        "precio_unit": total_pc,
        "descuento": 0,
    }


def _lineas_detalle_cero(payload: dict) -> list:
    out = []
    for it in (payload.get("items") or []):
        out.append({
            "producto": it.get("producto") or it.get("descripcion") or "",
            "observacion": it.get("observacion") or it.get("detalle") or "",
            "cantidad": 1,
            "precio_unit": 0,
            "descuento": 0,
        })
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Render PDF
# ──────────────────────────────────────────────────────────────────────────────
def render_pdf_from_payload(payload: dict) -> bytes:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape()
    )

    def money_ar(value):
        n = _to_float(value)
        s = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"$ {s}"

    env.filters["money"] = money_ar

    hoy = date.today()
    dias = int(_to_float((payload.get("meta") or {}).get("validez_dias") or 7))
    vto = hoy + timedelta(days=dias)

    meta = dict(payload.get("meta") or {})
    if not str(meta.get("numero") or "").strip():
        meta["numero"] = f"{random.randint(0, 9999):04d}"

    payload = dict(payload)
    payload["meta"] = meta

    # 🔥 USAMOS NUEVO SISTEMA
    totales = _calcular_totales(payload)

    # 👉 el resumen usa PRECIO LISTA
    lineas = [_linea_resumen(totales["total_PC"]), *_lineas_detalle_cero(payload)]

    html_str = env.get_template("presupuesto.html").render(
        payload=payload,
        empresa={
            "nombre": "The Gamer Shop",
            "cond_iva": "Responsable Inscripto",
            "cuit": "23-22364802-9",
            "ing_brutos": "0088520-07",
            "inicio_act": "21/10/1992",
            "domicilio": "Carhue 1409, CABA, Argentina",
            "cond_iva_cliente": "Consumidor Final",
        },
        hoy=hoy,
        vto=vto,
        lineas=lineas,

        # 🔥 IMPORTANTE
        totales=totales
    )

    base = os.path.join(app.root_path, "static")
    return HTML(string=html_str, base_url=base).write_pdf()


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/versions")
def versions():
    import weasyprint, pydyf
    try:
        target = pydyf.PDF if not hasattr(pydyf.PDF, "__init__") else pydyf.PDF.__init__
        sig = str(inspect.signature(target))
    except Exception:
        sig = "unknown"

    return {
        "weasyprint": getattr(weasyprint, "__version__", "unknown"),
        "pydyf": getattr(pydyf, "__version__", "unknown"),
        "pydyf_file": getattr(pydyf, "__file__", "unknown"),
        "pydyf_pdf_init": sig,
    }


@app.get("/presupuesto")
def info():
    return (
        "Use POST /presupuesto con JSON. Pruebe /demo para ver un PDF.",
        200,
        {"content-type": "text/plain; charset=utf-8"},
    )


@app.get("/demo")
def demo():
    sample = {
        "meta": {"titulo": "Presupuesto Demo"},
        "cliente": {"nombre": "Consumidor Final"},
        "items": [
            {"producto": "Procesador", "precio_unit": 351000},
            {"producto": "Motherboard", "precio_unit": 130000},
        ],
    }
    pdf = render_pdf_from_payload(sample)
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        download_name="demo.pdf"
    )


@app.post("/presupuesto")
def presupuesto():
    try:
        data = request.get_json(force=True, silent=True) or {}

        if isinstance(data.get("payload"), dict):
            data = data["payload"]

        if not isinstance(data.get("items"), list):
            data["items"] = []
        if not isinstance(data.get("meta"), dict):
            data["meta"] = {}
        if not isinstance(data.get("cliente"), dict):
            data["cliente"] = {}

        pdf_bytes = render_pdf_from_payload(data)
        nombre = (data.get("meta", {}).get("titulo") or "Presupuesto") + ".pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=nombre,
        )

    except Exception as e:
        app.logger.exception("Error en /presupuesto")
        return (f"SERVER ERROR: {e}", 500, {"Content-Type": "text/plain; charset=utf-8"})


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Running on http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=True)