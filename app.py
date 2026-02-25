import os
import requests
from flask import Flask, request, make_response
import google.generativeai as genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQ0ua0nxGVpZAdeM3N6ZAWIt8DLtINQA8AyesM8YumfTZAiZA6CTAZA3NzZAGKCK0J7eBRH0OZAunPDyNE2V2xZAN2bDjFX18ZCJBdoKaLWPZBZBxK7z3peZCTibFvzVxcEwK3vhgLNQtAl0Sp2jxsOWIiJ31c7rOUE7Vx716RmcZBkZAeU3OqZAGqW7PVW3KJaxk1UZCKVZC4YokIRtRZCUZC6PZCJftbEvO9DEnWoWMofqVvvSpeFgZCqcHxqe1ZCSJ3WOeZBudO9VD7B8oIysUaE5"
PHONE_ID = "993609860504120"
GEMINI_KEY = "AIzaSyCsCCwscxMzKPutn4HxD0Uq8WFRbP90Dp8"

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
    print(f"Respuesta de Meta: {r.status_code}")
    return r.status_code

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == TOKEN_VERIFICACION:
        return make_response(challenge, 200)
    return "Error", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            # --- LIMPIEZA DEL NÚMERO ---
            if numero_usuario.startswith("521") and len(numero_usuario) == 13:
                numero_usuario = "52" + numero_usuario[3:]
            
            print(f"Número corregido: {numero_usuario}")

            # --- CEREBRO ACTUALIZADO ---
            try:
                # El nombre 'gemini-1.5-flash' es el estándar actual
                model = genai.GenerativeModel('gemini-1.5-flash')
                respuesta_ia = model.generate_content(mensaje_usuario)
                texto_final = respuesta_ia.text
            except Exception as e_ia:
                print(f"Fallo Gemini 1.5: {e_ia}")
                # Segundo intento con modelo Pro si el Flash falla
                try:
                    model = genai.GenerativeModel('gemini-1.0-pro')
                    respuesta_ia = model.generate_content(mensaje_usuario)
                    texto_final = respuesta_ia.text
                except Exception as e_ia2:
                    print(f"Fallo total IA: {e_ia2}")
                    texto_final = "¡Hola! Ya puedo recibir tus mensajes, pero mi cerebro de IA está teniendo un pequeño ajuste técnico. Soy el asesor del Equipo 7."

            # Enviamos respuesta
            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        print(f"Error general: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=10000, host='0.0.0.0')
