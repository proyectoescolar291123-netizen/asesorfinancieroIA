import os
import requests
from flask import Flask, request, make_response
from google import genai
from google.genai import types 

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Esta es la forma definitiva de llamar al cliente para evitar el 404
client = genai.Client(api_key=GEMINI_KEY)
MODELO_ESTABLE = "gemini-1.5-flash"

usuarios_memoria = {}

def enviar_mensaje_whatsapp(texto, numero):
    numero_limpio = str(numero).replace("+", "")
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": numero_limpio, "type": "text", "text": {"body": texto}}
    r = requests.post(url, headers=headers, json=data)
    return r.status_code

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

@app.route("/")
def index(): return "Asesor Financiero v4.5 - Modelo Estable", 200

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
            numero_usuario = msg['from']
            tipo = msg['type']

            if numero_usuario not in usuarios_memoria:
                usuarios_memoria[numero_usuario] = {"estado": "PLAN", "perfil": "", "ventas": 0.0, "historial": []}
                enviar_mensaje_whatsapp("¡Hola! Soy tu Asistente Financiero 📊.\n\n¿Qué plan prefieres?\n🔹 *PLAN NORMAL*\n👑 *PLAN PREMIUM*", numero_usuario)
                return make_response("OK", 200)

            user = usuarios_memoria[numero_usuario]
            input_ia = ""

            # --- CAPTURA DE INPUT (VOZ O TEXTO) ---
            if tipo == "text":
                input_ia = msg['text']['body']
            elif tipo == "audio":
                path = descargar_audio(msg['audio']['id'])
                if path:
                    with open(path, "rb") as f:
                        response_audio = client.models.generate_content(
                            model=MODELO_ESTABLE,
                            contents=[types.Part.from_bytes(data=f.read(), mime_type="audio/ogg"),
                                     types.Part.from_text(text="Transcribe este audio de negocio.")]
                        )
                        input_ia = response_audio.text
                    os.remove(path)

            # --- LÓGICA DE NEGOCIO ---
            if user["estado"] == "PLAN":
                user["plan"] = input_ia
                user["estado"] = "ENCUESTA"
                encuesta = ("¡Excelente! 🚀 Responde estas preguntas:\n\n1️⃣ Giro\n2️⃣ Colonia\n3️⃣ ¿Nuevo?\n4️⃣ Renta 🏠\n5️⃣ Insumos 📦\n6️⃣ Impuestos 🏦\n7️⃣ Nómina 👥\n8️⃣ Empleados\n9️⃣ Ticket promedio\n🔟 Gastos fijos 💡\n1️⃣1️⃣ Meta ahorro")
                enviar_mensaje_whatsapp(encuesta, numero_usuario)
            
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = input_ia
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Registro completado! ✅ Reporta tus ventas o dudas.", numero_usuario)

            else:
                user["historial"].append(f"Usuario: {input_ia}")
                prompt = f"Eres Asesor Financiero EBC. Perfil: {user['perfil']}. Ventas: ${user['ventas']}. Historial: {user['historial'][-5:]}. Si hay venta, pon [SUMAR: monto]."
                
                response = client.models.generate_content(model=MODELO_ESTABLE, contents=prompt)
                res_ia = response.text

                if "[SUMAR:" in res_ia:
                    try:
                        monto = float(res_ia.split("[SUMAR:")[1].split("]")[0].strip())
                        user["ventas"] += monto
                        res_ia = res_ia.split("[SUMAR:")[0].strip() + f"\n\n💰 *Total: ${user['ventas']}*"
                    except: pass
                
                user["historial"].append(f"IA: {res_ia}")
                enviar_mensaje_whatsapp(res_ia, numero_usuario)

    except Exception as e: print(f"Error: {e}")
    return make_response("OK", 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
