import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQ6akRT0yrzKr9yERvShQZCZBG4MOgbrZC4hHbVYPB6ZBFZA8GMoabAkZActiHEzjyAZBbMzQ4SOsUDB84CqrqtKoZC8XSGNWZAhExMZBLXBHRqqsfVOZCVGq7c5KkI43kHR9ol4tZC3mZBkF1zKzH8rh4OZB5t3MwUbDKlCxQUfIktRQocbas68sZBgZCb4UKOHKvqB9U7io6MTVxaTzdF2mCuMNmthmpVlYmgVngJqvD1Wthjbc6ZBHpIVtKk9a9JSZCU8E1sCEerxagQTp6H"
PHONE_ID = "993609860504120"
GEMINI_KEY = "AIzaSyCsCCwscxMzKPutn4HxD0Uq8WFRbP90Dp8"

genai.configure(api_key=GEMINI_KEY)

# --- FUNCIÓN PARA ENVIAR ---
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
    print(f"Respuesta de Meta: {r.status_code} - {r.text}")
    return r.status_code

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
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            print(f"Mensaje de {numero_usuario}: {mensaje_usuario}")

            try:
                # Intentamos con el nombre de modelo más básico
                model = genai.GenerativeModel('gemini-pro')
                respuesta_ia = model.generate_content(mensaje_usuario)
                texto_final = respuesta_ia.text
            except Exception as e_ia:
                print(f"Fallo la IA: {e_ia}")
                texto_final = "Hola! Recibí tu mensaje pero mi cerebro de IA está tardando en responder. Intenta de nuevo."

            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        print(f"Error general: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=10000, host='0.0.0.0')
