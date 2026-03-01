import os
import requests
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

# --- 2. MEMORIA GLOBAL ---
usuarios_memoria = {}

# --- 3. FUNCIONES DE APOYO ---
def enviar_mensaje_whatsapp(texto, numero):
    numero_limpio = str(numero).replace("+", "")
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": numero_limpio,
        "type": "text",
        "text": {"body": texto}
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"DEBUG WHATSAPP: Status {r.status_code}")
    return r.status_code

def descargar_audio(media_id):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url_media = f"https://graph.facebook.com/v18.0/{media_id}"
    res = requests.get(url_media, headers=headers)
    file_url = res.json().get("url")
    if not file_url: return None
    archivo_binario = requests.get(file_url, headers=headers)
    path_local = f"{media_id}.ogg"
    with open(path_local, "wb") as f:
        f.write(archivo_binario.content)
    return path_local

@app.route("/")
def index():
    return "Asesor Financiero EBC - Sistema Premium Activo", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == TOKEN_VERIFICACION:
        return make_response(str(challenge), 200)
    return "Error de token", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        value = datos['entry'][0]['changes'][0]['value']
        if 'messages' in value:
            msg = value['messages'][0]
            numero_usuario = msg['from']
            tipo_mensaje = msg['type']

            if numero_usuario not in usuarios_memoria:
                usuarios_memoria[numero_usuario] = {
                    "estado": "ELIGE_PLAN",
                    "plan": "",
                    "perfil": "",
                    "ventas_hoy": 0.0,
                    "historial": []
                }
                bienvenida = (
                    "¡Hola! Soy tu Asistente Financiero 📊. Te ayudo a controlar el dinero de tu negocio.\n\n"
                    "¿Qué plan prefieres?\n"
                    "🔹 *PLAN NORMAL*\n"
                    "👑 *PLAN PREMIUM*\n\n"
                    "¿Con cuál te gustaría iniciar hoy?"
                )
                enviar_mensaje_whatsapp(bienvenida, numero_usuario)
                return make_response("OK", 200)

            user = usuarios_memoria[numero_usuario]
            mensaje_para_ia = ""

            if tipo_mensaje == "text":
                mensaje_para_ia = msg['text']['body']
            elif tipo_mensaje == "audio":
                media_id = msg['audio']['id']
                path_audio = descargar_audio(media_id)
                if path_audio:
                    with open(path_audio, "rb") as f:
                        audio_bytes = f.read()
                    try:
                        response_audio = client.models.generate_content(
                            model="gemini-1.5-flash",
                            contents=[
                                types.Part.from_text(text="Transcribe exactamente lo que dice este audio:"),
                                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
                            ]
                        )
                        mensaje_para_ia = response_audio.text
                    except:
                        mensaje_para_ia = "[Error al procesar audio]"
                    if os.path.exists(path_audio): os.remove(path_audio)

            # --- LÓGICA DE ESTADOS ---
            if user["estado"] == "ELIGE_PLAN":
                user["plan"] = mensaje_para_ia
                user["estado"] = "ENCUESTA"
                # MENSAJE DE REGISTRO FORMATEADO
                encuesta = (
                    "¡Excelente! 🚀 Para personalizar tus cálculos, responde estas preguntas:\n\n"
                    "1️⃣ ¿Giro del negocio? (Ej: Cafetería)\n"
                    "2️⃣ ¿Colonia?\n"
                    "3️⃣ ¿Es nuevo o ya tiene tiempo?\n"
                    "4️⃣ ¿Renta mensual? 🏠\n"
                    "5️⃣ ¿Inversión semanal en insumos? 📦\n"
                    "6️⃣ ¿Impuestos al mes? 🏦\n"
                    "7️⃣ ¿Nómina por quincena? 👥\n"
                    "8️⃣ ¿Cuántos empleados?\n"
                    "9️⃣ ¿Ticket promedio de venta?\n"
                    "🔟 ¿Gastos fijos (luz/agua/internet)? 💡\n"
                    "1️⃣1️⃣ ¿Meta de ahorro mensual?\n\n"
                    "*(Puedes responder todo en un solo mensaje)*"
                )
                enviar_mensaje_whatsapp(encuesta, numero_usuario)
            
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = mensaje_para_ia
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Registro completado! ✅ Ya tengo tus costos base. Reporta tus ventas o hazme cualquier duda.", numero_usuario)

            else:
                user["historial"].append(f"Usuario: {mensaje_para_ia}")
                historial_reciente = "\n".join(user["historial"][-6:])
                prompt_sistema = (
                    f"Eres un Asesor Financiero Pro. Perfil: {user['perfil']}. "
                    f"Ventas hoy: ${user['ventas_hoy']}. Historial:\n{historial_reciente}\n"
                    "Si detectas una venta, pon al final: [SUMAR: monto]."
                )
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt_sistema
                )
                respuesta_ia = response.text
                if "[SUMAR:" in respuesta_ia:
                    try:
                        monto = float(respuesta_ia.split("[SUMAR:")[1].split("]")[0].strip())
                        user["ventas_hoy"] += monto
                        respuesta_ia = respuesta_ia.split("[SUMAR:")[0].strip()
                        respuesta_ia += f"\n\n💰 *Total hoy: ${user['ventas_hoy']:.2f}*"
                    except: pass
                user["historial"].append(f"Asesor: {respuesta_ia}")
                enviar_mensaje_whatsapp(respuesta_ia, numero_usuario)

    except Exception as e: print(f"Error: {e}")
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
