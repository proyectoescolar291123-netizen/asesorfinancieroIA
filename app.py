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
MODELOS_A_PROBAR = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-3-flash-preview"]

usuarios_memoria = {}

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

@app.route("/")
def index(): return "Asesor Financiero v6.7 - Lenguaje Amigable", 200

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
                usuarios_memoria[numero_usuario] = {
                    "estado": "PLAN", "plan": "", "perfil": "", 
                    "efectivo": 0.0, "tarjeta": 0.0, "historial": []
                }
                bienvenida = (
                    "¡Qué onda! 👋 Soy tu Asistente Financiero. Te ayudo a llevar las cuentas de tu negocio sin complicaciones.\n\n"
                    "Dime, ¿qué plan te late?\n🔹 *PLAN NORMAL*\n👑 *KING PREMIUM*\n\n"
                    "¿Con cuál empezamos?"
                )
                enviar_mensaje_whatsapp(bienvenida, numero_usuario)
                return make_response("OK", 200)

            user = usuarios_memoria[numero_usuario]
            input_ia = ""

            if tipo == "text":
                input_ia = msg['text']['body']
            elif tipo == "audio":
                path = descargar_audio(msg['audio']['id'])
                if path:
                    with open(path, "rb") as f:
                        input_ia = llamar_gemini([types.Part.from_bytes(data=f.read(), mime_type="audio/ogg"),
                                                 types.Part.from_text(text="Transcribe este audio.")] )
                    os.remove(path)

            if user["estado"] == "PLAN":
                user["plan"] = input_ia.upper()
                user["estado"] = "ENCUESTA"
                encuesta = "¡Súper! 🚀 Oye, para ayudarte mejor con tus números, cuéntame:\n\n1️⃣ ¿De qué es tu negocio?\n2️⃣ ¿En qué colonia estás?\n3️⃣ ¿Apenas vas arrancando o ya llevas tiempo?\n4️⃣ ¿Cuánto pagas de renta? 🏠\n5️⃣ ¿Cuánto gastas a la semana en mercancía? 📦\n6️⃣ ¿Y de impuestos al mes?\n7️⃣ ¿Cuánto pagas de sueldos a la quincena? 👥\n8️⃣ ¿Cuántos empleados tienes?\n9️⃣ ¿Más o menos cuánto te compra cada cliente?\n🔟 ¿Gastos de luz, agua o internet? 💡\n1️⃣1️⃣ ¿Cuánto te gustaría ahorrar al mes?"
                enviar_mensaje_whatsapp(encuesta, numero_usuario)
            
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = input_ia
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Listo! ✅ Ya quedó tu registro. Avísame cuando vendas algo en efectivo o con tarjeta y yo llevo la cuenta por ti.", numero_usuario)

            else:
                user["historial"].append(f"Usuario: {input_ia}")
                
                # PROMPT CON LENGUAJE RELAJADO
                prompt = (
                    f"Eres un asesor financiero buena onda pero muy listo con los números. Perfil: {user['perfil']}. Plan: {user['plan']}. "
                    f"Saldos: Efectivo ${user['efectivo']}, Tarjeta ${user['tarjeta']}. "
                    f"Historial: {user['historial'][-5:]}. "
                    "\nINSTRUCCIONES:\n"
                    "1. Habla de forma sencilla, clara y amigable. Cero tecnicismos aburridos.\n"
                    "2. NO escribas el desglose de saldos, yo lo pondré al final.\n"
                    "3. Si el usuario vende algo, felicítalo como un compa: '¡Eso es todo!', '¡Venga!', '¡A darle!'.\n"
                    "4. Pon al final EXACTAMENTE: [EFECTIVO: monto] o [TARJETA: monto].\n"
                    "5. Si es PREMIUM, dale un consejo de negocio que sea fácil de entender y aplicar."
                )
                
                res_ia = llamar_gemini(prompt)

                if res_ia:
                    if "[EFECTIVO:" in res_ia:
                        try:
                            m = float(res_ia.split("[EFECTIVO:")[1].split("]")[0].strip())
                            user["efectivo"] += m
                            res_ia = res_ia.split("[EFECTIVO:")[0].strip()
                        except: pass
                    
                    if "[TARJETA:" in res_ia:
                        try:
                            m = float(res_ia.split("[TARJETA:")[1].split("]")[0].strip())
                            user["tarjeta"] += m
                            res_ia = res_ia.split("[TARJETA:")[0].strip()
                        except: pass
                    
                    total = user["efectivo"] + user["tarjeta"]
                    reporte = (
                        f"\n\n--- 📊 *REPORTE ACTUAL* ---\n"
                        f"💵 *Efectivo:* ${user['efectivo']:.2f}\n"
                        f"💳 *Tarjeta:* ${user['tarjeta']:.2f}\n"
                        f"💰 *Total:* ${total:.2f}"
                    )
                    
                    respuesta_final = res_ia + reporte
                    user["historial"].append(f"IA: {respuesta_final}")
                    enviar_mensaje_whatsapp(respuesta_final, numero_usuario)

    except Exception as e: print(f"Error: {e}")
    return make_response("OK", 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
