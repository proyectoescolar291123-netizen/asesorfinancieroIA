import os
import requests
from flask import Flask, request, make_response
from google import genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
# Este es el token que te funcionó en el curl
ACCESS_TOKEN = "EAANLEpqpXc0BQZBX1ButbAghEjtCqFbjYEiMToHVRNpCZC0lGyIiDm5GAW1zgTPoHLGkCVvq6yhFsm0thBOtOZBNd9XvjdMkvtURlNu93duJTov17c9pZAnvqP7TrZCxZBkSCHb7ZBDTU0cfCHUQNkK4c3AwxT6V1UgXI4vlDPC1Q0fxkPExQ0xHjBsxAZC9lqZC6odK4CHXK3mfI8vCcmEPVTbFZATSZAY8PaJt5ZCoNyKZA65Y8qesn1jZAMrrZAr7ilUJRJCmG93bqD6VZBejF2mktDUx"
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializamos el cliente
client = genai.Client(api_key=GEMINI_KEY)

def enviar_mensaje_whatsapp(texto, numero):
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    r = requests.post(url, headers=headers, json=data)
    # Imprimimos el resultado del envío para debug
    print(f"DEBUG WHATSAPP: Status {r.status_code} - Response: {r.text}")
    return r.status_code

@app.route("/")
def index():
    return "Asesor Financiero EBC - Gemini 3 Activo y Monitoreado", 200

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
        # Detectamos si es un mensaje de texto que llega
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            print(f"MENSAJE RECIBIDO de {numero_usuario}: {mensaje_usuario}")

            # --- LÓGICA CON GEMINI 3 FLASH ---
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=mensaje_usuario
                )
                texto_final = response.text
                print(f"IA RESPONDIÓ EXITOSAMENTE: {texto_final[:50]}...") # Solo los primeros 50 caracteres
            except Exception as e:
                print(f"Error con Gemini 3: {e}")
                # Respaldo
                try:
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=mensaje_usuario
                    )
                    texto_final = response.text
                except:
                    texto_final = "Hola! Soy tu asesor financiero. Mi sistema se está actualizando, ¿puedes repetir tu duda?"

            # Enviamos la respuesta
            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        # Esto nos dirá si Meta mandó algo que no era un mensaje (como un 'read receipt')
        pass
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
