import os
import re
import json
import hmac
import hashlib
import logging
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

import requests
from flask import Flask, request, make_response
from google import genai
from google.genai import types

# --- 0. LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("columba")

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = os.environ.get("WHATSAPP_VERIFY_TOKEN", "estudiante_ia_2026")
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "993609860504120")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v20.0")
DB_PATH = os.environ.get("DB_PATH", "/tmp/columba.db")

REQUIRED_ENV = {"WHATSAPP_TOKEN": ACCESS_TOKEN, "GEMINI_API_KEY": GEMINI_KEY}
faltantes = [k for k, v in REQUIRED_ENV.items() if not v]
if faltantes:
    log.error(f"Faltan variables de entorno obligatorias: {faltantes}")

client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# Prioridad: Lite responde en <800ms y evita los picos 503 del modelo 3.6
MODELOS_A_PROBAR = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]

_locks_usuarios = {}
_locks_lock = threading.Lock()


def lock_de(numero):
    with _locks_lock:
        if numero not in _locks_usuarios:
            _locks_usuarios[numero] = threading.Lock()
        return _locks_usuarios[numero]


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                numero TEXT PRIMARY KEY,
                estado TEXT NOT NULL,
                plan TEXT DEFAULT 'NORMAL',
                perfil TEXT DEFAULT '{}',
                efectivo REAL DEFAULT 0,
                tarjeta REAL DEFAULT 0,
                fechas_pago TEXT DEFAULT '',
                indice_pregunta INTEGER DEFAULT 0,
                fecha_registro TEXT DEFAULT CURRENT_TIMESTAMP,
                pendiente TEXT DEFAULT NULL,
                contador_movimientos INTEGER DEFAULT 0,
                premium_ofrecido INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL,
                medio TEXT NOT NULL,
                monto REAL NOT NULL,
                descripcion TEXT,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mensajes_procesados (
                msg_id TEXT PRIMARY KEY,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def ya_procesado(msg_id):
    with db() as conn:
        cur = conn.execute("SELECT 1 FROM mensajes_procesados WHERE msg_id = ?", (msg_id,))
        if cur.fetchone():
            return True
        conn.execute("INSERT INTO mensajes_procesados (msg_id) VALUES (?)", (msg_id,))
        return False


def obtener_usuario(numero):
    with db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE numero = ?", (numero,)).fetchone()
        return dict(row) if row else None


def crear_usuario(numero):
    with db() as conn:
        conn.execute(
            "INSERT INTO usuarios (numero, estado, plan, perfil) VALUES (?, 'ACTIVO', 'NORMAL', '{}')",
            (numero,),
        )


def actualizar_usuario(numero, **campos):
    if not campos:
        return
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [numero]
    with db() as conn:
        conn.execute(f"UPDATE usuarios SET {sets} WHERE numero = ?", valores)


def registrar_movimiento(numero, medio, monto, descripcion):
    with db() as conn:
        conn.execute(
            "INSERT INTO movimientos (numero, medio, monto, descripcion) VALUES (?, ?, ?, ?)",
            (numero, medio, monto, descripcion),
        )


def enviar_mensaje_whatsapp(texto, numero):
    numero_limpio = str(numero).replace("+", "")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": numero_limpio, "type": "text", "text": {"body": texto}}
    try:
        r = requests.post(url, headers=headers, json=data, timeout=8)
        if r.status_code >= 400:
            log.error(f"WhatsApp API error {r.status_code}: {r.text}")
        return r.status_code
    except Exception as e:
        log.error(f"Fallo de red WhatsApp: {e}")
        return None


def llamar_gemini(contenido_prompt, json_mode=False):
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    for nombre_modelo in MODELOS_A_PROBAR:
        try:
            response = client.models.generate_content(
                model=nombre_modelo, contents=contenido_prompt, config=config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            log.warning(f"Fallo en modelo {nombre_modelo}: {e}")
            continue
    log.error("Todos los modelos de Gemini fallaron.")
    return None


def transcribir_audio(media_id):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        url_media = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
        res = requests.get(url_media, headers=headers, timeout=8)
        if res.status_code >= 400:
            return None, True

        info = res.json()
        file_url = info.get("url")
        if not file_url:
            return None, True

        session = requests.Session()
        session.headers.update(headers)
        archivo = session.get(file_url, timeout=12)
        if archivo.status_code >= 400 or len(archivo.content) == 0:
            return None, True

        contenido = archivo.content
    except requests.RequestException:
        return None, True

    if client is None:
        return None, True

    mime_type = "audio/ogg"

    for nombre_modelo in MODELOS_A_PROBAR:
        try:
            response = client.models.generate_content(
                model=nombre_modelo,
                contents=[
                    types.Part.from_bytes(data=contenido, mime_type=mime_type),
                    types.Part.from_text(
                        text="Transcribe el audio textualmente en español. "
                             "Si menciona dinero o compras/ventas, conserva los números exactos. "
                             "Devuelve solo la transcripción limpia sin comentarios."
                    ),
                ],
            )
            texto = (response.text or "").strip()
            if texto:
                return texto, False
        except Exception as e:
            log.warning(f"Fallo audio con {nombre_modelo}: {e}")
            continue

    return None, True


def verificar_firma(payload_bytes, firma_header):
    if not APP_SECRET:
        return True
    if not firma_header:
        return False
    esperado = "sha256=" + hmac.new(APP_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma_header)


def procesar_y_responder(numero_usuario, tipo, msg, msg_id):
    if ya_procesado(msg_id):
        return

    with lock_de(numero_usuario):
        try:
            user = obtener_usuario(numero_usuario)

            input_usuario = ""
            error_audio = False

            if tipo == "text":
                input_usuario = msg["text"]["body"]
            elif tipo == "audio":
                input_usuario, error_audio = transcribir_audio(msg["audio"]["id"])

            input_usuario = (input_usuario or "").strip()

            if not input_usuario:
                if error_audio:
                    enviar_mensaje_whatsapp(
                        "🎙️ Hubo un retraso procesando la nota de voz. Por favor repítela brevemente.",
                        numero_usuario,
                    )
                else:
                    enviar_mensaje_whatsapp("No logré entender el mensaje 🙏 ¿Podrías repetirlo?", numero_usuario)
                return

            if input_usuario.lower() in ["reiniciar", "reset"]:
                actualizar_usuario(numero_usuario, estado="ACTIVO", efectivo=0.0, tarjeta=0.0, pendiente=None, contador_movimientos=0)
                enviar_mensaje_whatsapp("🔄 Balance reseteado a $0.00. Listo para tu demostración.", numero_usuario)
                return

            if user is None:
                crear_usuario(numero_usuario)
                bienvenida = (
                    "¡Hola! 👋 Soy tu Asistente Financiero *Columba IA*.\n\n"
                    "Llevo el control de tus ventas y gastos al momento. Solo dime qué vendiste o compraste por texto o nota de voz.\n\n"
                    "💡 *Prueba con:* 'Vendí 350 en efectivo' o 'Pagué 200 de luz con tarjeta'."
                )
                enviar_mensaje_whatsapp(bienvenida, numero_usuario)
                return

            if user["estado"] == "CONFIRMANDO":
                procesar_confirmacion(numero_usuario, user, input_usuario)
                return

            if re.search(r"\b(premium|plan premium|comprar)\b", input_usuario, re.I):
                actualizar_usuario(numero_usuario, plan="PREMIUM")
                enviar_mensaje_whatsapp(
                    "👑 *¡Plan Premium Activado!* ($59.90 MXN/mes)\n\n"
                    "Beneficios habilitados:\n"
                    "- Registro y balance por notas de voz 🎙️\n"
                    "- Reportes y gráficas para Excel 📊\n"
                    "- Recordatorios de nómina, renta e impuestos 📅",
                    numero_usuario
                )
                return

            procesar_operacion_financiera(numero_usuario, user, input_usuario)

        except Exception:
            log.exception(f"Error procesando a {numero_usuario}")


def procesar_operacion_financiera(numero_usuario, user, input_usuario):
    # Detección ultra-rápida local (Regex): si el usuario fue directo, no espera a Gemini
    match_num = re.search(r"(\d+(?:\.\d+)?)", input_usuario.replace(",", ""))
    texto_min = input_usuario.lower()
    palabras_venta = ["vendi", "vendí", "cobre", "cobré", "ingreso", "venta"]
    palabras_gasto = ["gaste", "gasté", "pague", "pagué", "compre", "compré", "renta", "luz", "gasto"]

    datos = None
    if match_num and (any(p in texto_min for p in palabras_venta) or any(p in texto_min for p in palabras_gasto)):
        tipo = "venta" if any(p in texto_min for p in palabras_venta) else "gasto"
        medio = "tarjeta" if "tarjeta" in texto_min else "efectivo"
        datos = {
            "es_movimiento": True,
            "tipo": tipo,
            "medio": medio,
            "monto": float(match_num.group(1)),
            "descripcion": input_usuario[:45]
        }
    else:
        # Si no hubo match directo, recurre a Gemini
        prompt_clasificacion = (
            "Eres clasificador contable rápido. Mensaje: "
            f"\"{input_usuario}\".\n"
            "Devuelve únicamente JSON:\n"
            '{"es_movimiento": true|false, "tipo": "venta"|"gasto"|null, "medio": "efectivo"|"tarjeta"|null, "monto": 100.0, "descripcion": "concepto"}'
        )
        respuesta_json = llamar_gemini(prompt_clasificacion, json_mode=True)
        if respuesta_json:
            try:
                limpio = re.sub(r"^```json|```$", "", respuesta_json.strip())
                datos = json.loads(limpio)
            except Exception:
                datos = None

    if datos and datos.get("es_movimiento") and datos.get("monto"):
        monto = abs(float(datos["monto"]))
        tipo = datos.get("tipo", "venta")
        medio = datos.get("medio", "efectivo")
        desc = datos.get("descripcion", "movimiento")

        pendiente = {"tipo": tipo, "medio": medio, "monto": monto, "descripcion": desc}
        actualizar_usuario(numero_usuario, pendiente=json.dumps(pendiente, ensure_ascii=False), estado="CONFIRMANDO")

        etiqueta = "Venta" if tipo == "venta" else "Gasto"
        enviar_mensaje_whatsapp(
            f"📝 *{etiqueta} detectada:* ${monto:.2f} en *{medio}* ({desc}).\n\n"
            "¿Deseas confirmarlo en tu balance? Responde *Sí* o *No*.",
            numero_usuario
        )
        return

    # Charla amigable breve
    prompt_charla = (
        f"Eres Columba IA. El usuario dice: '{input_usuario}'. "
        "Responde amigable en 1 línea corta y dile que puede decirte una venta o gasto."
    )
    texto = llamar_gemini(prompt_charla) or "¡Hola! Cuéntame qué vendiste o compraste hoy y lo anoto al balance. 📈"
    enviar_mensaje_whatsapp(texto.strip(), numero_usuario)


def procesar_confirmacion(numero_usuario, user, input_usuario):
    pendiente = json.loads(user["pendiente"] or "null")
    if not pendiente:
        actualizar_usuario(numero_usuario, estado="ACTIVO", pendiente=None)
        enviar_mensaje_whatsapp("No había movimiento pendiente. ¿Qué registramos? 👍", numero_usuario)
        return

    texto = input_usuario.strip().lower()
    es_afirmativo = bool(re.search(r"\b(si|sí|correcto|ok|va|simon|confirmo|yes)\b", texto))
    es_negativo = bool(re.search(r"\b(no|cancelar|descarta|mal)\b", texto))

    if es_afirmativo and not es_negativo:
        monto = pendiente["monto"]
        medio = pendiente["medio"]
        signo = 1 if pendiente["tipo"] == "venta" else -1
        delta = signo * monto

        efectivo = user["efectivo"] + (delta if medio == "efectivo" else 0)
        tarjeta = user["tarjeta"] + (delta if medio == "tarjeta" else 0)
        nuevo_contador = user["contador_movimientos"] + 1

        actualizar_usuario(
            numero_usuario,
            efectivo=efectivo,
            tarjeta=tarjeta,
            contador_movimientos=nuevo_contador,
            estado="ACTIVO",
            pendiente=None,
        )
        registrar_movimiento(numero_usuario, medio, delta, pendiente["descripcion"])

        total = efectivo + tarjeta
        reporte = (
            f"✅ *¡Registrado!*\n\n"
            f"--- 📊 *BALANCE EN TIEMPO REAL* ---\n"
            f"💵 *Efectivo:* ${efectivo:.2f}\n"
            f"💳 *Tarjeta:* ${tarjeta:.2f}\n"
            f"💰 *Total en caja:* ${total:.2f}"
        )
        enviar_mensaje_whatsapp(reporte, numero_usuario)

    elif es_negativo:
        actualizar_usuario(numero_usuario, estado="ACTIVO", pendiente=None)
        enviar_mensaje_whatsapp("🗑️ Operación descartada. ¿Qué otra venta o gasto deseas reportar?", numero_usuario)
    else:
        enviar_mensaje_whatsapp("Por favor responde *Sí* para guardar en el balance o *No* para descartar.", numero_usuario)


@app.route("/")
def index():
    return "Columba IA v10.4 - Ultra Fast", 200


@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    if request.args.get("hub.verify_token") == TOKEN_VERIFICACION:
        return make_response(str(request.args.get("hub.challenge")), 200)
    return "Error", 403


@app.route("/webhook", methods=["POST"])
def recibir_mensajes():
    firma = request.headers.get("X-Hub-Signature-256")
    if not verificar_firma(request.get_data(), firma):
        log.warning("Firma de webhook rechazada.")
        return make_response("Firma inválida", 403)

    datos = request.get_json(silent=True) or {}
    res = make_response("OK", 200)
    try:
        entry = datos.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        if "messages" in value:
            msg = value["messages"][0]
            thread = threading.Thread(
                target=procesar_y_responder,
                args=(msg["from"], msg["type"], msg, msg["id"]),
                daemon=True,
            )
            thread.start()
    except Exception:
        log.exception("Error en webhook")
    return res


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
