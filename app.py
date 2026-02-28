import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQwzEp5H6cZBxXVDfGnbcJoZA1n6oTQlmPkFxV0lBlvZAt3b1OeIcV98a5OtpvJiwf54wS8KUUdf1w9ZCZBuik1ebML181qyqZBWtLGfk5ZBgsiiDZAimaObqhrxVspZClavBIy3UvRUbYoyZBnxgrMXDRVUTI2hgR1ucYhVZBQPLlMFtLrBx6Bl6BoT8vUW27EMzZAI3Qf0qOZASkeEeWIM4e9PBCLTEqmO7QibRKNKTOmnIhlQh05uZBUv2zbARNZAzjXUkr6pTZCELP5hp"
PHONE_ID = "993609860504120"
GEMINI_KEY = "AIzaSyBwnf34jZjEixhRkB-k6iEZquNIzbcacfg"

genai.configure(api_key=GEMINI_KEY)

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
    return r.status_code

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == TOKEN_VERIFICACION:
        return make_response(str(challenge), 200)
    return "Error", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        # --- CAPTURAMOS EL MENSAJE ---
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

            # --- LÓGICA DE IA ---
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                respuesta_ia = model.generate_content(mensaje_usuario)
                texto_final = respuesta_ia.text
            except Exception as e:
                print(f"Error IA: {e}")
                texto_final = f"Error de IA: {str(e)[:50]}"

            # --- ENVIAMOS RESPUESTA ---
            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        print(f"Error general: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    # Render usa la variable de entorno PORT, si no existe usa el 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
