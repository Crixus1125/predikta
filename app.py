import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import openai

# Configuración inicial
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or 'clave-secreta-predikta-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
openai.api_key = os.getenv('OPENAI_API_KEY')

# Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    pais = db.Column(db.String(50))
    plan = db.Column(db.String(20), default='free')

# Página de inicio
@app.route('/')
def home():
    return render_template('index.html')

# Login (admin o usuario)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('correo', '').strip().lower()
        password = request.form.get('contrasena')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id

            # Verificamos si es admin
            if email == 'admin@predikta.com':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('panel'))

        flash('Correo o contraseña incorrectos', 'error')
    return render_template('login.html')

# Registro de usuario
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre_completo')
        email = request.form.get('email', '').strip().lower()
        password = generate_password_hash(request.form.get('password'))
        pais = request.form.get('pais')

        if not User.query.filter_by(email=email).first():
            new_user = User(nombre=nombre, email=email, password=password, pais=pais)
            db.session.add(new_user)
            db.session.commit()
            flash('Registro exitoso. Inicia sesión', 'success')
            return redirect(url_for('login'))

        flash('Este correo ya está registrado', 'error')
    return render_template('registro.html')

# Panel de usuario
@app.route('/panel')
def panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.email.strip().lower() == 'admin@predikta.com':
        return redirect(url_for('admin_panel'))

    return render_template('paneluser.html')

# Panel de administrador
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if user.email.strip().lower() != 'admin@predikta.com':
        flash('Acceso denegado: No eres administrador.', 'error')
        return redirect(url_for('panel'))

    return render_template('admin.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API de análisis
@app.route('/api/analizar', methods=['POST'])
def analizar():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    data = request.get_json()
    tipo_trading = data.get("tipo_trading", "ninguno").lower().strip()
    tipo_senal = data.get("tipo_senal", "directa").lower().strip()
    prompt_usuario = data.get("prompt", "")
    imagen_base64 = data.get("imagen", "")

    if not imagen_base64:
        return jsonify({"error": "No se recibió imagen"}), 400

    if tipo_trading == "cazador":
        estilo = "modo Cazador: detectar trampas, manipulación institucional y errores de la masa"
    elif tipo_trading == "day":
        estilo = "Day Trading: operar intradía usando temporalidades cortas como 15m, 30m, 1h"
    elif tipo_trading == "swing":
        estilo = "Swing Trading: operar movimientos de 1 a varios días con patrones técnicos y volumen"
    elif tipo_trading == "scalping":
        estilo = "Scalping: entradas rápidas en temporalidades 1m, 2m, 5m"
    else:
        estilo = "estilo libre"

    refuerzo = ""
    if "completa" in tipo_senal or ("tp" in tipo_senal and "sl" in tipo_senal):
        refuerzo = f"""
IMPORTANTE:
Cuando se solicita una señal COMPLETA, debes entregar 3 precios obligatorios:
1. Precio de entrada
2. Take Profit
3. Stop Loss

Ejemplo de formato obligatorio:
SEÑAL: BUY @ 32820  
TAKE PROFIT: 32900  
STOP LOSS: 32750

Ahora genera la señal real con base en el gráfico e incluye el análisis técnico basado en el estilo: {estilo}.
"""

    prompt_final = refuerzo + "\n" + prompt_usuario

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un analista técnico profesional. Comienza siempre con el bloque de señal. Luego analiza el gráfico."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_final},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + imagen_base64.split(",")[1]}}
                    ]
                }
            ],
            temperature=0.6,
            max_tokens=1500
        )

        resultado = response.choices[0].message.content
        return jsonify({"respuesta": resultado})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Inicializador
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@predikta.com').first():
            admin = User(
                nombre='Admin Predikta',
                email='admin@predikta.com',
                password=generate_password_hash('admin123'),
                pais='Predikta'
            )
            db.session.add(admin)
            db.session.commit()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
