import os
import requests
from flask import Flask, request, make_response

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQx9TPkHZBWbkGyu88I4Jdg68UZAUndbCiseBdOnQ560KlMHsVcZC389ThFqiHqbdkjZBkDf4g1HajE3z3MNikd7yIXY3jy8TP1yzkaWZARASAw3GkjB7n22GdvHlgVNjZANh4azd4xENZAZBqgivQLzvk7jQ03gt64WaOJaroPcwSRXfXlkGJYjjhjGpUsExOhmgnUn9JIuaAL8uYw9fJ6VEFPswDEofxKeSzr8RnAErt0ZAqZAGlcOCFScjrR0TlP5M7TaANF0ertNgZDZD"
PHONE_ID = "993609860504120"
# Forzamos la lectura de la clave desde el inicio
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Mensaje de control para saber que el servidor arrancó bien
print(f"--- Servidor Iniciado ---")
if GEMINI_KEY:
    print("LOG: GEMINI_API_KEY detectada en el sistema.")
else:
    print("LOG: ERROR - No se detectó GEMINI_API_KEY.")

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

@app.route("/")
def index():
    return "Servidor del Asesor Financiero está Activo", 200

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

            # --- LÓGICA DE IA (DIRECTA A V1) ---
            try:
                # Usamos Gemini 1.5 Pro que es más estable para estas peticiones
                url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": mensaje_usuario}]}]
                }
                res = requests.post(url_gemini, json=payload)
                res_data = res.json()

                if 'candidates' in res_data:
                    texto_final = res_data['candidates'][0]['content']['parts'][0]['text']
                else:
                    # Si da error, imprimimos la respuesta completa de Google para saber qué pasó
                    print(f"Error de Google API: {res_data}")
                    texto_final = "Hola! Mi cerebro financiero está en mantenimiento un segundo. ¿Me repites tu duda?"
            except Exception as e:
                print(f"Error procesando IA: {e}")
                texto_final = "Hubo un error técnico. ¡Intenta de nuevo!"

            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        print(f"Error general: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
