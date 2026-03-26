import sqlite3
import hashlib
import os

DB_FILE = "triage_hospital.db"

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

def create_tables():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS triage_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_registro TEXT NOT NULL,
        tipo_registro TEXT NOT NULL DEFAULT 'Inicial',
        folio TEXT,
        nombre_paciente TEXT,
        edad INTEGER,
        sexo TEXT,
        motivo_consulta TEXT,
        usuario_captura TEXT,
        rol_usuario TEXT,
        fecha_hora_ingreso TEXT,
        flujo_clinico TEXT NOT NULL DEFAULT 'General',
        frecuencia_cardiaca INTEGER,
        frecuencia_respiratoria INTEGER,
        presion_sistolica INTEGER,
        presion_diastolica INTEGER,
        temperatura REAL,
        saturacion_oxigeno INTEGER,
        glucosa_capilar INTEGER,
        dolor_eva INTEGER,
        estado_conciencia TEXT,
        dolor_toracico INTEGER,
        dificultad_respiratoria INTEGER,
        fiebre INTEGER,
        sangrado_activo INTEGER,
        convulsiones INTEGER,
        alteracion_mental INTEGER,
        debilidad_unilateral INTEGER,
        alteracion_habla INTEGER,
        asimetria_facial INTEGER,
        inicio_subito INTEGER,
        sincope INTEGER,
        palidez_diaforesis INTEGER,
        trauma_reciente INTEGER,
        antecedente_hipertension INTEGER,
        antecedente_diabetes INTEGER,
        puede_caminar INTEGER,
        embarazo INTEGER DEFAULT 0,
        semanas_gestacion INTEGER DEFAULT 0,
        sangrado_vaginal INTEGER DEFAULT 0,
        dolor_pelvico INTEGER DEFAULT 0,
        hipertension_embarazo INTEGER DEFAULT 0,
        cefalea_intensa INTEGER DEFAULT 0,
        vision_borrosa INTEGER DEFAULT 0,
        movimientos_fetales_disminuidos INTEGER DEFAULT 0,
        sepsis_score INTEGER DEFAULT 0,
        sepsis_alerta TEXT DEFAULT '',
        semaforo TEXT,
        accion_sugerida TEXT,
        motivos TEXT,
        alertas TEXT,
        estado_operativo TEXT NOT NULL DEFAULT 'Pendiente'
    )
    """)

    conn.commit()
    conn.close()

def create_default_user():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    username = "admin"
    full_name = "Administrador"
    role = "Administrador"
    password = "Admin1234"
    salt = os.urandom(16).hex()
    password_hash = hash_password(password, salt)

    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    existing = cur.fetchone()
    if not existing:
        cur.execute(
            "INSERT INTO users (username, full_name, role, salt, password_hash) VALUES (?, ?, ?, ?, ?)",
            (username, full_name, role, salt, password_hash),
        )
        print("Usuario creado:")
        print("usuario: admin")
        print("contraseña: Admin1234")
    else:
        print("El usuario admin ya existe.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    create_default_user()
    print(f"Base de datos lista: {DB_FILE}")
