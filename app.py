from flask import Flask, request, make_response

app = Flask(__name__)

# AQUÍ PONES EL TOKEN QUE TÚ INVENTES
TOKEN_VERIFICACION = "estudiante_ia_2026"

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    # Meta envía una petición GET para validar
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == TOKEN_VERIFICACION:
        return make_response(challenge, 200)
    return make_response("Error de validación", 403)

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    # Aquí llegarán los mensajes de WhatsApp
    datos = request.get_json()
    print("Mensaje recibido:", datos)
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    app.run(port=5000)
