import os
import requests
import threading
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
# Priorizamos Gemini 3 Flash por disponibilidad en México
MODELOS_A_PROBAR = ["gemini-3-flash-preview", "gemini-1.5-flash-latest", "gemini-1.5-flash"]

usuarios_memoria = {}

# --- 2. FUNCIONES DE APOYO ---
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

# --- 3. LÓGICA PRINCIPAL (HILO SEPARADO) ---
def procesar_y_responder(numero_usuario, tipo, msg):
    try:
        if numero_usuario not in usuarios_memoria:
            usuarios_memoria[numero_usuario] = {
                "estado": "PLAN", "plan": "", "perfil": "", 
                "efectivo": 0.0, "tarjeta": 0.0, "historial": [],
                "fechas_pago": ""
            }
            bienvenida = (
                "¡Hola! 👋 Soy tu Asistente Financiero para la EBC.\n\n"
                "Controla tus finanzas por voz o texto.\n\n"
                "🌟 *PLAN GRATIS:* Registro de ventas/gastos y saldo diario.\n"
                "👑 *PLAN PREMIUM:* Todo lo anterior + Resúmenes en PDF 📄, Gráficas 📊, "
                "y recordatorios de Nóminas, Impuestos y Renta 📅.\n\n"
                "¿Con qué plan empezamos?\n1️⃣ *PLAN GRATIS*\n2️⃣ *PLAN PREMIUM*"
            )
            enviar_mensaje_whatsapp(bienvenida, numero_usuario)
            return

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

        # Lógica de estados
        if user["estado"] == "PLAN":
            user["plan"] = "PREMIUM" if "PREMIUM" in input_ia.upper() or "2" in input_ia else "GRATIS"
            user["estado"] = "ENCUESTA"
            encuesta = "¡Excelente elección! 🚀 Para configurar tu tablero, cuéntame:\n\n1️⃣ Giro del negocio\n2️⃣ Colonia\n3️⃣ ¿Pagas renta?"
            enviar_mensaje_whatsapp(encuesta, numero_usuario)
        
        elif user["estado"] == "ENCUESTA":
            user["perfil"] = input_ia
            if user["plan"] == "PREMIUM":
                user["estado"] = "FECHAS_PREMIUM"
                pregunta_fechas = (
                    "✨ *Configuración Premium:* Para tus recordatorios, dime:\n\n"
                    "📅 ¿Qué días pagas nómina?\n🏠 ¿Qué día pagas renta?\n💡 ¿Qué días pagas servicios (Luz, Agua, Gas)?"
                )
                enviar_mensaje_whatsapp(pregunta_fechas, numero_usuario)
            else:
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Listo! ✅ Ya puedes reportar tus VENTAS o GASTOS.", numero_usuario)

        elif user["estado"] == "FECHAS_PREMIUM":
            user["fechas_pago"] = input_ia
            user["estado"] = "ACTIVO"
            enviar_mensaje_whatsapp("¡Configuración Premium completa! 👑 Ya puedes reportar tus VENTAS o GASTOS.", numero_usuario)

        else:
            # FLUJO ACTIVO: Registro de transacciones
            user["historial"].append(f"Usuario: {input_ia}")
            prompt = (
                f"Eres un Asesor Financiero experto. Perfil: {user['perfil']}. Plan: {user['plan']}. "
                f"Fechas especiales: {user['fechas_pago']}. "
                f"Saldo actual: Efectivo ${user['efectivo']}, Tarjeta ${user['tarjeta']}. "
                f"Historial: {user['historial'][-3:]}. "
                "\nINSTRUCCIONES:\n"
                "1. Ventas = montos POSITIVOS. Gastos/Pagos = montos NEGATIVOS.\n"
                "2. Si es una venta mixta, sepáralas.\n"
                "3. Al final usa SIEMPRE: [EFECTIVO: monto] y/o [TARJETA: monto].\n"
                "4. Si el plan es PREMIUM, da un consejo proactivo sobre sus fechas de pago si son próximas."
            )
            
            res_ia = llamar_gemini(prompt)

            if res_ia:
                # Procesamiento de saldos (Suma de positivos y negativos)
                for medio in ["EFECTIVO", "TARJETA"]:
                    tag = f"[{medio}:"
                    if tag in res_ia:
                        try:
                            partes = res_ia.split(tag)
                            for p in partes[1:]:
                                monto = float(p.split("]")[0].strip())
                                if medio == "EFECTIVO": user["efectivo"] += monto
                                else: user["tarjeta"] += monto
                        except: pass
                
                # Limpiar la respuesta para el usuario
                respuesta_limpia = res_ia.split("[EFECTIVO:")[0].split("[TARJETA:")[0].strip()
                
                total = user["efectivo"] + user["tarjeta"]
                reporte = (
                    f"\n\n--- 📊 *REPORTE ACTUAL* ---\n"
                    f"💵 *Efectivo:* ${user['efectivo']:.2f}\n"
                    f"💳 *Tarjeta:* ${user['tarjeta']:.2f}\n"
                    f"💰 *Balance:* ${total:.2f}"
                )
                
                respuesta_final = respuesta_limpia + reporte
                user["historial"].append(f"IA: {respuesta_final}")
                enviar_mensaje_whatsapp(respuesta_final, numero_usuario)
                
    except Exception as e:
        print(f"Error en hilo: {e}")

# --- 4. RUTAS ---
@app.route("/")
def index(): return "Asesor Financiero EBC v7.0 - Premium Activo", 200

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
            thread = threading.Thread(target=procesar_y_responder, args=(numero_usuario, tipo, msg))
            thread.start()
    except Exception as e: print(f"Error Webhook: {e}")
    return make_response("OK", 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
