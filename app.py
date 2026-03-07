import os
import requests
import threading
import re
from flask import Flask, request, make_response
from google import genai
from google.genai import types 

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_KEY)
MODELOS_A_PROBAR = ["gemini-3-flash-preview", "gemini-1.5-flash-latest"]

usuarios_memoria = {}
mensajes_procesados = set()

# --- 2. PREGUNTAS DE LA ENCUESTA ---
PREGUNTAS_ENCUESTA = [
    "1️⃣ ¿En qué consiste tu negocio? (Ej: Cafetería, hostal, papelería).",
    "2️⃣ ¿En qué colonia se encuentra?",
    "3️⃣ ¿Es un negocio nuevo o ya tiene tiempo en la zona?",
    "4️⃣ ¿Cuánto pagas de renta al mes? 🏠",
    "5️⃣ ¿Cuánto inviertes en insumos a la semana? 📦",
    "6️⃣ ¿Cuánto pagas de impuestos al mes? 🏦",
    "7️⃣ ¿Cuánto pagas de nómina por quincena? 👥",
    "8️⃣ ¿Cuántos empleados tienes?",
    "9️⃣ ¿Cuál es tu ticket promedio de venta? (Lo que gasta un cliente promedio).",
    "🔟 ¿A cuánto ascienden tus recibos de luz, agua e internet al mes? 💡",
    "1️⃣1️⃣ ¿Tienes alguna meta de ahorro o reinversión mensual? 💰"
]

# --- 3. FUNCIONES DE APOYO ---
def enviar_mensaje_whatsapp(texto, numero):
    numero_limpio = str(numero).replace("+", "")
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": numero_limpio, "type": "text", "text": {"body": texto}}
    r = requests.post(url, headers=headers, json=data)
    return r.status_code

def llamar_gemini(contenido_prompt):
    for nombre_modelo in MODELOS_A_PROBAR:
        try:
            response = client.models.generate_content(model=nombre_modelo, contents=contenido_prompt)
            return response.text
        except: continue
    return None

def descargar_audio(media_id):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url_media = f"https://graph.facebook.com/v18.0/{media_id}"
    res = requests.get(url_media, headers=headers)
    file_url = res.json().get("url")
    if not file_url: return None
    archivo = requests.get(file_url, headers=headers)
    path = f"{media_id}.ogg"
    with open(path, "wb") as f: f.write(archivo.content)
    return path

# --- 4. LÓGICA PRINCIPAL ---
def procesar_y_responder(numero_usuario, tipo, msg, msg_id):
    if msg_id in mensajes_procesados: return
    mensajes_procesados.add(msg_id)

    try:
        if numero_usuario not in usuarios_memoria:
            usuarios_memoria[numero_usuario] = {
                "estado": "PLAN", "plan": "", "perfil": "", 
                "efectivo": 0.0, "tarjeta": 0.0, "historial": [],
                "fechas_pago": "", "indice_pregunta": 0
            }
            bienvenida = (
                "¡Hola! 👋 Soy tu Asistente Financiero Columba IA.\n\n"
                "¿Con qué plan empezamos?\n\n"
                "1️⃣ *PLAN NORMAL*: Registro de ventas/gastos. 📉\n"
                "2️⃣ *PLAN PREMIUM*: PDFs, Gráficas y Recordatorios. 👑"
            )
            enviar_mensaje_whatsapp(bienvenida, numero_usuario)
            return

        user = usuarios_memoria[numero_usuario]
        input_usuario = ""

        if tipo == "text":
            input_usuario = msg['text']['body']
        elif tipo == "audio":
            path = descargar_audio(msg['audio']['id'])
            if path:
                with open(path, "rb") as f:
                    input_usuario = llamar_gemini([types.Part.from_bytes(data=f.read(), mime_type="audio/ogg"),
                                                 types.Part.from_text(text="Transcribe este audio.")] )
                os.remove(path)

        # --- FLUJO DE ESTADOS ---
        if user["estado"] == "PLAN":
            user["plan"] = "PREMIUM" if "PREMIUM" in input_usuario.upper() or "2" in input_usuario else "NORMAL"
            user["estado"] = "ENCUESTA"
            enviar_mensaje_whatsapp(f"¡Excelente! Elegiste el plan {user['plan']}. 🚀\n\nConfiguraremos tu perfil. Responde estas preguntas una por una:\n\n" + PREGUNTAS_ENCUESTA[0], numero_usuario)

        elif user["estado"] == "ENCUESTA":
            idx = user["indice_pregunta"]
            user["perfil"] += f"P{idx+1}: {input_usuario} | "
            
            if idx + 1 < len(PREGUNTAS_ENCUESTA):
                user["indice_pregunta"] += 1
                enviar_mensaje_whatsapp(PREGUNTAS_ENCUESTA[user["indice_pregunta"]], numero_usuario)
            else:
                if user["plan"] == "PREMIUM":
                    user["estado"] = "FECHAS_PREMIUM"
                    enviar_mensaje_whatsapp("👑 *Premium:* ¿Qué días pagas nómina, renta y servicios? (Para recordatorios 📅)", numero_usuario)
                else:
                    user["estado"] = "ACTIVO"
                    enviar_mensaje_whatsapp("✅ ¡Perfil listo! Ya puedes reportar tus ventas o gastos.", numero_usuario)

        elif user["estado"] == "FECHAS_PREMIUM":
            user["fechas_pago"] = input_usuario
            user["estado"] = "ACTIVO"
            enviar_mensaje_whatsapp("👑 ¡Configuración Premium lista! 🚀 Ya puedes empezar.", numero_usuario)

        else:
            # OPERACIÓN ACTIVA
            prompt = (
                f"Asesor Financiero. Perfil: {user['perfil']}. Plan: {user['plan']}. "
                f"Saldos: Efe ${user['efectivo']}, Tarj ${user['tarjeta']}. "
                f"Usuario dice: {input_usuario}. "
                "\nINSTRUCCIONES:\n"
                "1. Ventas = (+) Gastos = (-).\n"
                "2. Genera UNA SOLA VEZ al final: [EFECTIVO: monto] o [TARJETA: monto].\n"
                "3. Da un consejo breve con emojis.\n"
                "4. Al final añade: '💡 *Puedes preguntarme:*' y 3 sugerencias cortas basadas en su perfil."
            )
            
            res_ia = llamar_gemini(prompt)

            if res_ia:
                montos = re.findall(r"\[(EFECTIVO|TARJETA):\s*(-?\d+\.?\d*)\]", res_ia)
                for medio, monto_str in montos:
                    monto = float(monto_str)
                    if medio == "EFECTIVO": user["efectivo"] += monto
                    else: user["tarjeta"] += monto
                
                respuesta_visual = re.sub(r"\[.*?\]", "", res_ia).strip()
                reporte = (
                    f"\n\n--- 📊 *BALANCE* ---\n"
                    f"💵 *Efe:* ${user['efectivo']:.2f} | 💳 *Tarj:* ${user['tarjeta']:.2f}\n"
                    f"💰 *Total:* ${user['efectivo'] + user['tarjeta']:.2f}"
                )
                enviar_mensaje_whatsapp(respuesta_visual + reporte, numero_usuario)

    except Exception as e: print(f"Error: {e}")

# --- 5. RUTAS ---
@app.route("/")
def index(): return "Columba IA v9.5 - Live", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    if request.args.get('hub.verify_token') == TOKEN_VERIFICACION:
        return make_response(str(request.args.get('hub.challenge')), 200)
    return "Error", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        value = datos['entry'][0]['changes'][0]['value']
        if 'messages' in value:
            msg = value['messages'][0]
            thread = threading.Thread(target=procesar_y_responder, args=(msg['from'], msg['type'], msg, msg['id']))
            thread.start()
    except: pass
    return make_response("OK", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
