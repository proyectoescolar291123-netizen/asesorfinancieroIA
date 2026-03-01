import os
import requests
from flask import Flask, request, make_response
from google import genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
# Tu nuevo token actualizado
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializamos el cliente de Gemini 3
client = genai.Client(api_key=GEMINI_KEY)

# --- 2. MEMORIA GLOBAL ---
# Aquí guardamos perfil, ventas e historial por número de teléfono
usuarios_memoria = {}

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

@app.route("/")
def index():
    return "Asesor Financiero EBC - Cerebro con Memoria Activo", 200

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
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

            # --- INICIALIZACIÓN DE USUARIO NUEVO ---
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

            # --- PASO 1: ELECCIÓN DE PLAN ---
            if user["estado"] == "ELIGE_PLAN":
                user["plan"] = mensaje_usuario
                user["estado"] = "ENCUESTA"
                encuesta = (
                    "¡Excelente! 🚀 Ahora, responde estas preguntas de registro para conocer tu negocio:\n\n"
                    "1️⃣ Giro 2️⃣ Colonia 3️⃣ ¿Nuevo o con tiempo? 4️⃣ Renta 5️⃣ Insumos/semana 6️⃣ Impuestos 7️⃣ Nómina/quincena "
                    "8️⃣ Empleados 9️⃣ Ticket promedio 🔟 Gastos fijos (luz/agua) 1️⃣1️⃣ Meta de ahorro"
                )
                enviar_mensaje_whatsapp(encuesta, numero_usuario)

            # --- PASO 2: REGISTRO DE PERFIL ---
            elif user["estado"] == "ENCUESTA":
                user["perfil"] = mensaje_usuario
                user["estado"] = "ACTIVO"
                enviar_mensaje_whatsapp("¡Registro completado! ✅ Ahora soy tu socio financiero. Reporta tus ventas o hazme cualquier consulta.", numero_usuario)

            # --- PASO 3: MODO ASESOR ACTIVO (CEREBRO) ---
            else:
                # Agregamos el mensaje actual al historial
                user["historial"].append(f"Usuario: {mensaje_usuario}")
                
                # Preparamos el contexto para Gemini (historial + perfil + ventas)
                historial_reciente = "\n".join(user["historial"][-6:]) # Recordar últimos 6 mensajes
                prompt_sistema = (
                    f"Actúa como un Asesor Financiero experto. Perfil del negocio: {user['perfil']}. "
                    f"Plan contratado: {user['plan']}. Ventas del día: ${user['ventas_hoy']}.\n"
                    f"Historial de conversación:\n{historial_reciente}\n\n"
                    "INSTRUCCIÓN: Si el usuario reporta una venta, al final de tu respuesta pon EXACTAMENTE el formato: [SUMAR: monto]. "
                    "Responde de forma ejecutiva y ayuda al usuario con sus finanzas."
                )

                try:
                    response = client.models.generate_content(
                        model="gemini-3-flash-preview",
                        contents=prompt_sistema
                    )
                    respuesta_ia = response.text

                    # Lógica de Suma Automática si la IA detectó dinero
                    if "[SUMAR:" in respuesta_ia:
                        try:
                            monto_str = respuesta_ia.split("[SUMAR:")[1].split("]")[0].strip()
                            monto = float(monto_str)
                            user["ventas_hoy"] += monto
                            # Limpiamos el código para que el usuario no lo vea
                            respuesta_ia = respuesta_ia.split("[SUMAR:")[0].strip()
                            respuesta_ia += f"\n\n💰 *Total ventas del día: ${user['ventas_hoy']:.2f}*"
                        except:
                            pass

                    # Guardamos la respuesta de la IA en el historial
                    user["historial"].append(f"Asesor: {respuesta_ia}")
                    enviar_mensaje_whatsapp(respuesta_ia, numero_usuario)

                except Exception as e:
                    print(f"Error Gemini: {e}")
                    enviar_mensaje_whatsapp("Lo siento, tuve un problema al procesar eso. ¿Me lo repites?", numero_usuario)

    except Exception as e:
        print(f"Error General: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
