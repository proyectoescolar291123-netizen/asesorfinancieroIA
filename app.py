import os
import requests
from flask import Flask, request, make_response
from google import genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
# Token actualizado
ACCESS_TOKEN = "EAANLEpqpXc0BQZBX1ButbAghEjtCqFbjYEiMToHVRNpCZC0lGyIiDm5GAW1zgTPoHLGkCVvq6yhFsm0thBOtOZBNd9XvjdMkvtURlNu93duJTov17c9pZAnvqP7TrZCxZBkSCHb7ZBDTU0cfCHUQNkK4c3AwxT6V1UgXI4vlDPC1Q0fxkPExQ0xHjBsxAZC9lqZC6odK4CHXK3mfI8vCcmEPVTbFZATSZAY8PaJt5ZCoNyKZA65Y8qesn1jZAMrrZAr7ilUJRJCmG93bqD6VZBejF2mktDUx"
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializamos el cliente
client = genai.Client(api_key=GEMINI_KEY)

def enviar_mensaje_whatsapp(texto, numero):
    # Limpiamos el número de cualquier '+' por si acaso
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
    # DEBUG CRÍTICO: Esto nos dirá si Meta aceptó el envío
    print(f"DEBUG WHATSAPP: Enviando a {numero_limpio} - Status {r.status_code}")
    print(f"RESPUESTA META: {r.text}")
    return r.status_code

@app.route("/")
def index():
    return "Asesor Financiero EBC - Sistema Operativo v3.0", 200

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
        # Verificamos que sea un mensaje de texto
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            print(f"--- NUEVO MENSAJE RECIBIDO ---")
            print(f"De: {numero_usuario}")
            print(f"Contenido: {mensaje_usuario}")

            # --- LÓGICA CON GEMINI 3 FLASH PREVIEW ---
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=mensaje_usuario
                )
                texto_final = response.text
                print(f"IA GENERÓ RESPUESTA CORRECTAMENTE")
            except Exception as e:
                print(f"Error con Gemini 3: {e}")
                # Respaldo a Gemini 1.5 Flash
                try:
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=mensaje_usuario
                    )
                    texto_final = response.text
                except:
                    texto_final = "Hola! Soy tu asesor financiero de la EBC. Estoy procesando mucha información, ¿podrías repetir tu pregunta?"

            # Enviamos la respuesta de vuelta
            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        # Ignoramos notificaciones que no son mensajes (como confirmaciones de lectura)
        pass
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
