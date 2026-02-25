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
        # Extraemos el mensaje y el número que nos escribe
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            # --- LIMPIEZA DEL NÚMERO (IMPORTANTE PARA MÉXICO) ---
            # Si el número tiene 13 dígitos y empieza con 521, le quitamos el '1'
            if numero_usuario.startswith("521") and len(numero_usuario) == 13:
                # Esto cambia 52155... por 5255...
                numero_usuario = "52" + numero_usuario[3:]
            
            print(f"Número procesado para responder: {numero_usuario}")

            # Generamos respuesta con Gemini
            model = genai.GenerativeModel('gemini-pro')
            respuesta_ia = model.generate_content(mensaje_usuario)
            
            # Enviamos la respuesta de la IA
            enviar_mensaje_whatsapp(respuesta_ia.text, numero_usuario)
            
    except Exception as e:
        print(f"Error procesando el mensaje: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=10000, host='0.0.0.0')
