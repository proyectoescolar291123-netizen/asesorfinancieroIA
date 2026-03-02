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
def index(): return "Asesor Financiero v6.8 - Lenguaje Natural Activo", 200

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
                    "¡Hola! 👋 Soy tu Asistente Financiero. Te ayudo a llevar el control de tu negocio de forma sencilla.\n\n"
                    "Dime, ¿con qué plan empezamos?\n🔹 *PLAN NORMAL*\n👑 *KING PREMIUM*"
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
                encuesta = "¡Excelente! 🚀 Para darte mejores consejos, cuéntame un poco de tu negocio:\n\n1️⃣ Giro 2️⃣ Colonia 3️⃣ ¿Nuevo? 4️⃣ Renta 🏠 5️⃣ Insumos 📦 6️⃣ Impuestos 7️⃣ Sueldos 8️⃣ Empleados 9️⃣ Ticket promedio 🔟 Gastos fijos 1️⃣1️⃣ Meta ahorro"
                enviar_mensaje_whatsapp(encuesta, numero_usuario)
            
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = input_ia
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Listo! ✅ Registro completo. Ahora puedes reportar tus ventas por aquí.", numero_usuario)

            else:
                user["historial"].append(f"Usuario: {input_ia}")
                
                # --- PROMPT MEJORADO: LENGUAJE NATURAL Y SUMA ESTRICTA ---
                prompt = (
                    f"Eres un Asesor Financiero experto y amable. Perfil: {user['perfil']}. Plan: {user['plan']}. "
                    f"Saldo actual: Efectivo ${user['efectivo']}, Tarjeta ${user['tarjeta']}. "
                    f"Historial: {user['historial'][-5:]}. "
                    "\nINSTRUCCIONES:\n"
                    "1. Usa lenguaje natural, claro y profesional. Evita tecnicismos complejos y también evita ser demasiado informal o 'barrio'.\n"
                    "2. Si el usuario reporta ventas mixtas (efectivo y tarjeta), sepáralas.\n"
                    "3. Al final de tu mensaje usa SIEMPRE el formato: [EFECTIVO: monto] y/o [TARJETA: monto] para cada cantidad mencionada.\n"
                    "4. NO escribas el desglose de saldos totales en tu texto, solo confirma la acción.\n"
                    "5. Si el plan es PREMIUM, da un breve consejo sobre cómo mejorar la rentabilidad."
                )
                
                res_ia = llamar_gemini(prompt)

                if res_ia:
                    # PROCESAR EFECTIVO
                    if "[EFECTIVO:" in res_ia:
                        try:
                            # Puede haber varios montos, sumamos todos
                            partes = res_ia.split("[EFECTIVO:")
                            for p in partes[1:]:
                                monto = float(p.split("]")[0].strip())
                                user["efectivo"] += monto
                            res_ia = res_ia.split("[EFECTIVO:")[0].strip()
                        except: pass
                    
                    # PROCESAR TARJETA
                    if "[TARJETA:" in res_ia:
                        try:
                            partes = res_ia.split("[TARJETA:")
                            for p in partes[1:]:
                                monto = float(p.split("]")[0].strip())
                                user["tarjeta"] += monto
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
