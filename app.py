from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import traceback
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave-secreta'

def init_db():
    with sqlite3.connect('patients.db') as conn:
        # Crear tabla de pacientes con doctor
        conn.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correo TEXT,
                nombres TEXT,
                edad INTEGER,
                estatura REAL,
                peso REAL,
                fecha TEXT,
                descripcion TEXT,
                activo BOOLEAN DEFAULT 1,
                doctor TEXT
            )
        ''')

        # Crear tabla de pacientes eliminados
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pacientes_eliminados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER,
                nombres TEXT,
                correo TEXT,
                fecha_eliminacion TEXT,
                datos_completos TEXT,
                doctor TEXT
            )
        ''')

        # Crear trigger para guardar pacientes eliminados
        conn.execute('DROP TRIGGER IF EXISTS registro_eliminacion')
        conn.execute('''
            CREATE TRIGGER registro_eliminacion
            AFTER DELETE ON patients
            BEGIN
                INSERT INTO pacientes_eliminados (
                    paciente_id, nombres, correo, fecha_eliminacion, datos_completos, doctor
                )
                VALUES (
                    OLD.id,
                    OLD.nombres,
                    OLD.correo,
                    datetime('now'),
                    json_object(
                        'id', OLD.id,
                        'correo', OLD.correo,
                        'nombres', OLD.nombres,
                        'edad', OLD.edad,
                        'estatura', OLD.estatura,
                        'peso', OLD.peso,
                        'fecha', OLD.fecha,
                        'descripcion', OLD.descripcion,
                        'doctor', OLD.doctor
                    ),
                    OLD.doctor
                );
            END;
        ''')

        # Crear vista para pacientes activos
        conn.execute('''
            CREATE VIEW IF NOT EXISTS patient_view AS
            SELECT correo, nombres, edad, estatura, peso, descripcion, doctor
            FROM patients
            WHERE activo = 1
        ''')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    if email == 'admin' and password == '1234':
        session['user'] = email
        return redirect(url_for('appointments'))
    else:
        return render_template('index.html', error="Credenciales incorrectas")
    
@app.route('/appointments')
def appointments():
    if 'user' not in session:
        return redirect(url_for('index'))
    with sqlite3.connect('patients.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients WHERE activo = 1")
        patients = cur.fetchall()
    return render_template('appointments.html', patients=patients)


@app.route('/patient_login', methods=['POST'])
def patient_login():
    email = request.form['email']
    password = request.form['password']
    session['patient'] = email
    return redirect(url_for('patient_info'))


@app.route('/patients')
def patients():
    if 'user' not in session:
        return redirect(url_for('index'))
    with sqlite3.connect('patients.db') as conn:
        patients = conn.execute('''
            SELECT id, correo, nombres, edad, estatura, peso, fecha, descripcion, doctor 
            FROM patients 
            WHERE activo = 1
            ORDER BY id ASC
        ''').fetchall()
    return render_template('patients.html', patients=patients)

@app.route('/search_patient', methods=['GET', 'POST'])
def search_patient():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nombre = request.form['nombres']
        with sqlite3.connect('patients.db') as conn:
            pacientes = conn.execute('''
                SELECT id, correo, nombres, edad, estatura, peso, fecha, descripcion, 
                       COALESCE(doctor, 'No asignado') as doctor 
                FROM patients 
                WHERE nombres LIKE ? AND activo = 1
                ORDER BY nombres
            ''', (f'%{nombre}%',)).fetchall()

            eliminados = conn.execute('''
                SELECT nombres, correo, fecha_eliminacion, 
                       COALESCE(doctor, 'No asignado') as doctor 
                FROM pacientes_eliminados 
                WHERE nombres LIKE ?
                ORDER BY fecha_eliminacion DESC
            ''', (f'%{nombre}%',)).fetchall()

        return render_template('search_patient.html', 
                               patients=pacientes, 
                               eliminados=eliminados,
                               nombre=nombre)
    
    return render_template('search_patient.html')

@app.route('/patient_info', methods=['GET', 'POST'])
def patient_info():
    if request.method == 'POST':
        nombre = request.form['nombres']
        correo = request.form['correo']
        with sqlite3.connect('patients.db') as conn:
            paciente = conn.execute('''
                SELECT nombres, edad, estatura, peso, descripcion, doctor 
                FROM patients 
                WHERE nombres = ? AND correo = ? AND activo = 1
            ''', (nombre, correo)).fetchone()

            eliminado = conn.execute('''
                SELECT nombres, fecha_eliminacion, doctor 
                FROM pacientes_eliminados 
                WHERE nombres = ? AND correo = ?
            ''', (nombre, correo)).fetchone()
        
        return render_template('patient_search.html', 
                               patient=paciente, 
                               eliminado=eliminado,
                               nombre=nombre, 
                               correo=correo)
    return render_template('patient_search.html')

@app.route('/patient_search')
def patient_search():
    return render_template('patient_search.html')

@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        doctor = request.form.get('doctor', '').strip()
        if not doctor:
            return render_template('add_patient.html', error="Debe especificar un médico tratante")
        
        data = (
            request.form['correo'],
            request.form['nombres'],
            request.form['edad'],
            request.form['estatura'],
            request.form['peso'],
            request.form['fecha'],
            request.form['descripcion'],
            doctor
        )

        with sqlite3.connect('patients.db') as conn:
            try:
                conn.execute('''
                    INSERT INTO patients (correo, nombres, edad, estatura, peso, fecha, descripcion, doctor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)
                return redirect(url_for('patients'))
            except sqlite3.IntegrityError as e:
                return render_template('add_patient.html', error=f"Error al guardar paciente: {str(e)}")
    
    return render_template('add_patient.html')

@app.route('/delete_patient', methods=['GET', 'POST'])
def delete_patient():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        patient_id = request.form['id']
        with sqlite3.connect('patients.db') as conn:
            try:
                paciente = conn.execute('SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
                if paciente:
                    conn.execute('DELETE FROM patients WHERE id = ?', (patient_id,))
            except Exception as e:
                print(f"Error al eliminar paciente: {e}")
        return redirect(url_for('patients'))
    
    return render_template('delete_patient.html')

@app.route('/deleted_patients')
def deleted_patients():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    with sqlite3.connect('patients.db') as conn:
        eliminados = conn.execute('''
            SELECT paciente_id, nombres, correo, fecha_eliminacion, doctor 
            FROM pacientes_eliminados 
            ORDER BY fecha_eliminacion DESC
        ''').fetchall()
    
    return render_template('deleted_patients.html', eliminados=eliminados)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    try:
        init_db()
        app.run(debug=True)
    except Exception:
        print("ERROR CRÍTICO DETECTADO:")
        traceback.print_exc()
        print("Revisa la configuración del servidor o la base de datos.")
