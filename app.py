import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN (RELLENA ESTO CON TUS DATOS) ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQ0EO7FpcFZBhoZB3lBpBJOZCWJAU648KgbfoVRZBpARQWbTVZCLEf88bqG64JTX4tNrnpIqfNbIp4RpRo1BAxmSmkhq53NnGuVrA9bhpMgw172Gg98DSqZAvqcCZBSiYOLZB6XVgOWNoJ4grosZABkTt2Wpur7LXfg5oF8mJUU915MbHDygWkItWRQnRyWcuCQ0MYGGuebyuRWZB2XF1ElBdMjx0A5O4cyw77dtZC1Cj30n8td8ZA7ZCZB3YjX7LGV4I1WD7t5ZCfLcZCuyW"
PHONE_ID = "993609860504120"
GEMINI_KEY = "AIzaSyCsCCwscxMzKPutn4HxD0Uq8WFRbP90Dp8"

# Configuración de Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

PROMPT_SISTEMA = (
    "Eres un asesor financiero experto para micronegocios. "
    "Responde de forma breve y ayuda con dudas contables."
)

# --- 2. FUNCIÓN PARA ENVIAR EL MENSAJE ---
def enviar_mensaje_whatsapp(texto, numero):
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code

# --- 3. RUTAS DEL SERVIDOR ---
@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == TOKEN_VERIFICACION:
        return make_response(challenge, 200)
    return "Error", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    print("Datos recibidos:", datos) # Esto saldrá en los logs de Render
    
    try:
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

            # Generar respuesta con la IA
            respuesta_ia = model.generate_content(f"{PROMPT_SISTEMA}\nUsuario: {mensaje_usuario}")
            
            # Enviar de vuelta a WhatsApp
            enviar_mensaje_whatsapp(respuesta_ia.text, numero_usuario)
            
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=5000)
