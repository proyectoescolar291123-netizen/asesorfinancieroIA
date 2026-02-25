import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN (RELLENA ESTO) ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQ0EO7FpcFZBhoZB3lBpBJOZCWJAU648KgbfoVRZBpARQWbTVZCLEf88bqG64JTX4tNrnpIqfNbIp4RpRo1BAxmSmkhq53NnGuVrA9bhpMgw172Gg98DSqZAvqcCZBSiYOLZB6XVgOWNoJ4grosZABkTt2Wpur7LXfg5oF8mJUU915MbHDygWkItWRQnRyWcuCQ0MYGGuebyuRWZB2XF1ElBdMjx0A5O4cyw77dtZC1Cj30n8td8ZA7ZCZB3YjX7LGV4I1WD7t5ZCfLcZCuyW"
PHONE_ID = "993609860504120"
GEMINI_KEY = "AIzaSyCsCCwscxMzKPutn4HxD0Uq8WFRbP90Dp8"

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

PROMPT_SISTEMA = (
    "Eres un asesor financiero experto para micronegocios. "
    "Ayuda a gestionar ingresos, gastos y da consejos contables sencillos."
)

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
    try:
        # Extraer mensaje y número del usuario
        mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
        numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

        # Consultar a la IA
        chat = model.start_chat(history=[])
        respuesta_ia = chat.send_message(f"{PROMPT_SISTEMA}\nUsuario dice: {mensaje_usuario}")
        
        # Enviar respuesta de vuelta a WhatsApp
        enviar_mensaje_whatsapp(respuesta_ia.text, numero_usuario)
        
    except Exception as e:
        print("Error procesando mensaje:", e)
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=5000)
