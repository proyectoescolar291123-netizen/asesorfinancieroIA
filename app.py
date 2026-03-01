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

# LISTA DE MODELOS POR ORDEN DE PRIORIDAD (Blindada contra 404)
MODELOS_A_PROBAR = [
    "gemini-1.5-flash-latest", 
    "gemini-1.5-flash", 
    "gemini-3-flash-preview"
]

usuarios_memoria = {}

# --- 2. FUNCIONES DE APOYO ---
def enviar_mensaje_whatsapp(texto, numero):
    numero_limpio = str(numero).replace("+", "")
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": numero_limpio, "type": "text", "text": {"body": texto}}
    r = requests.post(url, headers=headers, json=data)
    print(f"DEBUG WHATSAPP: Status {r.status_code}")
    return r.status_code

def llamar_gemini(contenido_prompt):
    """Prueba diferentes nombres de modelos hasta que uno funcione"""
    for nombre_modelo in MODELOS_A_PROBAR:
        try:
            response = client.models.generate_content(model=nombre_modelo, contents=contenido_prompt)
            print(f"LOG: Gemini respondió usando {nombre_modelo}")
            return response.text
        except Exception as e:
            print(f"Fallo con {nombre_modelo}: {e}")
            continue
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

# --- 3. RUTAS ---
@app.route("/")
def index(): return "Asesor Financiero v5.5 - Blindado y Multimodal", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    if request.args.get('hub.verify_token') == TOKEN_VERIFICACION:
        return make_response(str(request.args.get('hub.challenge')), 200)
    return "Error de token", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        value = datos['entry'][0]['changes'][0]['value']
        if 'messages' in value:
            msg = value['messages'][0]
            numero_usuario = msg['from']
            tipo = msg['type']

            # Inicialización de usuario nuevo
            if numero_usuario not in usuarios_memoria:
                usuarios_memoria[numero_usuario] = {"estado": "PLAN", "perfil": "", "ventas": 0.0, "historial": []}
                bienvenida = (
                    "¡Hola! Soy tu Asistente Financiero 📊. Te ayudo a controlar el dinero de tu negocio directamente por aquí.\n\n"
                    "¿Qué plan prefieres para empezar?\n\n"
                    "🔹 *PLAN NORMAL*\n"
                    "• Mensajes ilimitados 💬\n"
                    "• Registro diario de ventas 💰\n"
                    "• Cálculo de ganancias y pérdidas 📉\n"
                    "• Apartado automático para tu renta 🏠\n\n"
                    "👑 *KING PREMIUM*\n"
                    "• Todo lo del Plan Normal ✅\n"
                    "• Tu propio Google Sheets sincronizado 📊\n"
                    "• Gráficas automáticas fáciles de entender 📈\n"
                    "• Análisis avanzado de tu negocio 🚀\n\n"
                    "¿Con cuál te gustaría iniciar hoy?"
                )
                enviar_mensaje_whatsapp(bienvenida, numero_usuario)
                return make_response("OK", 200)

            user = usuarios_memoria[numero_usuario]
            input_ia = ""

            # Captura de input (Voz o Texto)
            if tipo == "text":
                input_ia = msg['text']['body']
            elif tipo == "audio":
                path = descargar_audio(msg['audio']['id'])
                if path:
                    with open(path, "rb") as f:
                        input_ia = llamar_gemini([
                            types.Part.from_bytes(data=f.read(), mime_type="audio/ogg"),
                            types.Part.from_text(text="Transcribe exactamente lo que dice este audio de negocio:")
                        ])
                    os.remove(path)

            # --- FLUJO DE ESTADOS ---
            if user["estado"] == "PLAN":
                user["plan"] = input_ia
                user["estado"] = "ENCUESTA"
                encuesta = (
                    "¡Excelente elección! 🚀 Para personalizar tu Asistente y que mis cálculos sean exactos, necesito completar tu registro inicial.\n\n"
                    "Por favor, responde estas breves preguntas:\n"
                    "1️⃣ ¿Giro del negocio? (Ej: Cafetería)\n2️⃣ ¿Colonia?\n3️⃣ ¿Es nuevo o ya tiene tiempo?\n4️⃣ ¿Renta mensual? 🏠\n"
                    "5️⃣ ¿Inversión semanal en insumos? 📦\n6️⃣ ¿Impuestos al mes? 🏦\n7️⃣ ¿Nómina por quincena? 👥\n8️⃣ ¿Cuántos empleados?\n"
                    "9️⃣ ¿Ticket promedio de venta?\n🔟 ¿Gastos fijos (luz/agua/internet)? 💡\n1️⃣1️⃣ ¿Meta de ahorro mensual?"
                )
                enviar_mensaje_whatsapp(encuesta, numero_usuario)
            
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = input_ia
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Registro completado! ✅ Ya tengo tus costos base cargados. Ahora, cada vez que vendas algo o tengas un gasto, dímelo y yo llevaré tu control.", numero_usuario)

            else:
                user["historial"].append(f"Usuario: {input_ia}")
                prompt = (
                    f"Eres un Asesor Financiero Pro de la EBC. Perfil: {user['perfil']}. "
                    f"Ventas acumuladas hoy: ${user['ventas']}. "
                    f"Historial reciente: {user['historial'][-5:]}. "
                    "Instrucción: Si el usuario reporta una venta, calcula el nuevo total y felicítalo. "
                    "IMPORTANTE: Al final de tu respuesta pon exactamente este formato: [SUMAR: monto]"
                )
                
                res_ia = llamar_gemini(prompt)

                if res_ia:
                    if "[SUMAR:" in res_ia:
                        try:
                            monto = float(res_ia.split("[SUMAR:")[1].split("]")[0].strip())
                            user["ventas"] += monto
                            res_ia = res_ia.split("[SUMAR:")[0].strip() + f"\n\n💰 *Ventas totales del día: ${user['ventas']}*"
                        except: pass
                    
                    user["historial"].append(f"IA: {res_ia}")
                    enviar_mensaje_whatsapp(res_ia, numero_usuario)
                else:
                    enviar_mensaje_whatsapp("❌ Lo siento, tuve un problema conectando con el servidor de Google. Inténtalo en un momento.", numero_usuario)

    except Exception as e: 
        print(f"Error Crítico: {e}")
    return make_response("OK", 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
