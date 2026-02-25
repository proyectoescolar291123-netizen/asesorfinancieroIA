import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN (Pega tus datos aquí) ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
GEMINI_API_KEY = "AIzaSyCsCCwscxMzKPutn4HxD0Uq8WFRbP90Dp8"
WHATSAPP_TOKEN = "EAANLEpqpXc0BQ83xiPz0UaG0vehQLptWtoZAnULcAi4JKFO5mpECkyjd9FmLyM6f6NCNZBdEzGoQzyTgZA0cmyoLH0QaXE1AjYSK6yHyWpmyY8pxLHnoHD1I8hKXWZAkDPxESJZCWm8NDm6dDTEGRS6VWYQJX2jwsBPfVGlaFyCWKFk5V6Gyh6qo6X1X7ZCjxDn8ZBpVJEXtPlRcZASsOhi3BeNNU0vZBpTB2NuhMKVIEgrbthj6rVIftr6aVIndZAw64xkgnnZC56AljAjLVmLJfNb"
PHONE_NUMBER_ID = "993609860504120"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

PROMPT_SISTEMA = (
    "Eres un asesor financiero experto para micronegocios. "
    "Responde de forma breve, sencilla y amable. Ayuda con dudas de gastos e ingresos. "
    "Si te piden registrar algo, di que lo has anotado (aunque por ahora solo sea texto)."
)

def enviar_mensaje_whatsapp(texto, movil):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": movil,
        "type": "text",
        "text": {"body": texto}
    }
    response = requests.post(url, json=data, headers=headers)
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
        # Extraemos el mensaje y el número del que escribe
        mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
        numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

        # La IA procesa la respuesta
        chat = model.start_chat(history=[])
        respuesta_ia = chat.send_message(f"{PROMPT_SISTEMA}\nUsuario: {mensaje_usuario}")
        
        # Enviamos la respuesta de vuelta a WhatsApp
        enviar_mensaje_whatsapp(respuesta_ia.text, numero_usuario)
        
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=5000)
