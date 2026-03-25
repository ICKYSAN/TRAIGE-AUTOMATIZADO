import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

DB_FILE = "triage_hospital.db"

st.set_page_config(
    page_title="TRIAGE IA HOSPITAL",
    page_icon="🏥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .orange-box {background-color: #fff7ed; border-left: 8px solid #f97316; padding: 1rem; border-radius: 0.8rem;}
    .yellow-box {background-color: #fefce8; border-left: 8px solid #eab308; padding: 1rem; border-radius: 0.8rem;}
    .green-box {background-color: #f0fdf4; border-left: 8px solid #22c55e; padding: 1rem; border-radius: 0.8rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@dataclass
class TriageInput:
    folio: str
    nombre_paciente: str
    edad: int
    sexo: str
    motivo_consulta: str
    usuario_captura: str
    rol_usuario: str
    fecha_hora_ingreso: str

    frecuencia_cardiaca: int
    frecuencia_respiratoria: int
    presion_sistolica: int
    presion_diastolica: int
    temperatura: float
    saturacion_oxigeno: int
    glucosa_capilar: int
    dolor_eva: int
    estado_conciencia: str

    dolor_toracico: bool
    dificultad_respiratoria: bool
    fiebre: bool
    sangrado_activo: bool
    convulsiones: bool
    alteracion_mental: bool
    debilidad_unilateral: bool
    alteracion_habla: bool
    asimetria_facial: bool
    inicio_subito: bool
    sincope: bool
    palidez_diaforesis: bool
    trauma_reciente: bool
    antecedente_hipertension: bool
    antecedente_diabetes: bool
    puede_caminar: bool


def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, full_name, role, salt, password_hash, is_active
        FROM users
        WHERE username = ?
    """, (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    user = {
        "id": row[0],
        "username": row[1],
        "full_name": row[2],
        "role": row[3],
        "salt": row[4],
        "password_hash": row[5],
        "is_active": row[6],
    }

    if user["is_active"] != 1:
        return None

    candidate_hash = hash_password(password, user["salt"])
    if candidate_hash == user["password_hash"]:
        return user

    return None


def create_user(username: str, full_name: str, role: str, password: str):
    conn = get_conn()
    cur = conn.cursor()

    salt = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()[:32]
    password_hash = hash_password(password, salt)

    cur.execute("""
        INSERT INTO users (username, full_name, role, salt, password_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (username, full_name, role, salt, password_hash))

    conn.commit()
    conn.close()


def resultado(
    semaforo: str,
    accion: str,
    motivos: List[str],
    alertas: List[str],
    data: TriageInput
) -> Dict[str, Any]:
    return {
        "folio": data.folio,
        "nombre_paciente": data.nombre_paciente,
        "semaforo": semaforo,
        "accion_sugerida": accion,
        "motivos": motivos,
        "alertas": alertas,
        "datos_capturados": asdict(data),
        "aviso_legal": (
            "Herramienta de apoyo para priorización clínica. "
            "No sustituye la valoración médica ni el juicio clínico del personal de salud."
        ),
    }


def evaluar_triage(data: TriageInput) -> Dict[str, Any]:
    alertas: List[str] = []
    motivos: List[str] = []
    estado_conciencia = data.estado_conciencia.strip().lower()

    if estado_conciencia == "inconsciente":
        motivos.append("Paciente inconsciente")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.convulsiones:
        motivos.append("Convulsiones activas o recientes")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.saturacion_oxigeno < 90:
        motivos.append(f"Saturación de oxígeno crítica: {data.saturacion_oxigeno}%")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.presion_sistolica < 90:
        motivos.append(f"Hipotensión: TA sistólica {data.presion_sistolica} mmHg")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.sangrado_activo:
        motivos.append("Sangrado activo")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.dificultad_respiratoria and data.saturacion_oxigeno < 90:
        motivos.append("Dificultad respiratoria con desaturación")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.frecuencia_respiratoria > 30:
        motivos.append(f"Taquipnea severa: FR {data.frecuencia_respiratoria}")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.inicio_subito and (
        data.alteracion_habla or data.debilidad_unilateral or data.asimetria_facial
    ):
        motivos.append("Déficit neurológico súbito")
        if data.alteracion_habla:
            motivos.append("Alteración del habla")
        if data.debilidad_unilateral:
            motivos.append("Debilidad unilateral")
        if data.asimetria_facial:
            motivos.append("Asimetría facial")
        alertas.append("Código Cerebro")
        return resultado(
            "NARANJA",
            "Activar protocolo neurológico / valoración inmediata",
            motivos,
            alertas,
            data,
        )

    if data.dolor_toracico and data.palidez_diaforesis and (
        data.presion_sistolica < 90 or data.saturacion_oxigeno < 94
    ):
        motivos.append("Dolor torácico con datos de alto riesgo")
        if data.palidez_diaforesis:
            motivos.append("Palidez o diaforesis")
        alertas.append("Código Infarto")
        return resultado(
            "NARANJA",
            "Activar protocolo cardiovascular / valoración inmediata",
            motivos,
            alertas,
            data,
        )

    if estado_conciencia == "confuso" and not data.puede_caminar:
        motivos.append("Confusión con incapacidad funcional")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    sepsis_criterios = 0
    if data.temperatura > 38 or data.temperatura < 36:
        sepsis_criterios += 1
    if data.frecuencia_cardiaca > 90:
        sepsis_criterios += 1
    if data.frecuencia_respiratoria > 22:
        sepsis_criterios += 1
    if data.alteracion_mental or estado_conciencia in ["somnoliento", "confuso"]:
        sepsis_criterios += 1

    if sepsis_criterios >= 3:
        motivos.append("Sospecha de sepsis")
        motivos.append(f"Criterios positivos: {sepsis_criterios}")
        alertas.append("Código Sepsis")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if 90 <= data.saturacion_oxigeno <= 93:
        motivos.append(f"Saturación limítrofe: {data.saturacion_oxigeno}%")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.frecuencia_cardiaca > 120:
        motivos.append(f"Taquicardia: FC {data.frecuencia_cardiaca}")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.frecuencia_respiratoria > 22:
        motivos.append(f"Taquipnea: FR {data.frecuencia_respiratoria}")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if estado_conciencia in ["somnoliento", "confuso"] or data.alteracion_mental:
        motivos.append("Alteración del estado mental no crítica")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dolor_toracico:
        motivos.append("Dolor torácico sin criterios de máxima prioridad")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dificultad_respiratoria:
        motivos.append("Dificultad respiratoria leve a moderada")
        alertas.append("Compromiso respiratorio")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dolor_eva >= 5:
        motivos.append(f"Dolor significativo EVA {data.dolor_eva}/10")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.fiebre:
        motivos.append("Fiebre")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.trauma_reciente:
        motivos.append("Trauma reciente con estabilidad hemodinámica")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.glucosa_capilar < 70 or data.glucosa_capilar > 250:
        motivos.append(f"Glucosa alterada: {data.glucosa_capilar} mg/dL")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    motivos.append("Paciente estable, sin datos de alarma mayores")
    return resultado("VERDE", "Atención diferida", motivos, alertas, data)


def save_triage(data: TriageInput, res: Dict[str, Any]):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO triage_records (
            fecha_registro, folio, nombre_paciente, edad, sexo, motivo_consulta,
            usuario_captura, rol_usuario, fecha_hora_ingreso,
            frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
            temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
            dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
            alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
            inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
            antecedente_hipertension, antecedente_diabetes, puede_caminar,
            semaforo, accion_sugerida, motivos, alertas
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.folio,
        data.nombre_paciente,
        data.edad,
        data.sexo,
        data.motivo_consulta,
        data.usuario_captura,
        data.rol_usuario,
        data.fecha_hora_ingreso,
        data.frecuencia_cardiaca,
        data.frecuencia_respiratoria,
        data.presion_sistolica,
        data.presion_diastolica,
        data.temperatura,
        data.saturacion_oxigeno,
        data.glucosa_capilar,
        data.dolor_eva,
        data.estado_conciencia,
        int(data.dolor_toracico),
        int(data.dificultad_respiratoria),
        int(data.fiebre),
        int(data.sangrado_activo),
        int(data.convulsiones),
        int(data.alteracion_mental),
        int(data.debilidad_unilateral),
        int(data.alteracion_habla),
        int(data.asimetria_facial),
        int(data.inicio_subito),
        int(data.sincope),
        int(data.palidez_diaforesis),
        int(data.trauma_reciente),
        int(data.antecedente_hipertension),
        int(data.antecedente_diabetes),
        int(data.puede_caminar),
        res["semaforo"],
        res["accion_sugerida"],
        " | ".join(res["motivos"]),
        " | ".join(res["alertas"]) if res["alertas"] else ""
    ))

    conn.commit()
    conn.close()


def load_triage_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM triage_records ORDER BY id DESC", conn)
    conn.close()
    return df


def load_users_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, username, full_name, role, is_active, created_at
        FROM users
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()


if not st.session_state.logged_in:
    st.title("🔐 Login - TRIAGE IA HOSPITAL")

    tab_login, tab_register = st.tabs(["Iniciar sesión", "Crear usuario"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            login_btn = st.form_submit_button("Entrar")

        if login_btn:
            user = authenticate_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.success("Acceso correcto")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

        st.info("Usuario inicial: admin | Contraseña inicial: Admin1234")

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Nuevo usuario")
            new_full_name = st.text_input("Nombre completo")
            new_role = st.selectbox("Rol", ["Enfermería", "Médico", "Supervisor", "Administrador"])
            new_password = st.text_input("Nueva contraseña", type="password")
            register_btn = st.form_submit_button("Crear usuario")

        if register_btn:
            try:
                create_user(new_username, new_full_name, new_role, new_password)
                st.success("Usuario creado correctamente")
            except sqlite3.IntegrityError:
                st.error("Ese usuario ya existe")
            except Exception as e:
                st.error(f"Error al crear usuario: {e}")

else:
    user = st.session_state.user

    st.sidebar.success(f"Sesión activa: {user['full_name']}")
    st.sidebar.write(f"Rol: {user['role']}")
    if st.sidebar.button("Cerrar sesión"):
        logout()

    tab1, tab2, tab3 = st.tabs(["Triage", "Dashboard", "Usuarios"])

    with tab1:
        st.title("🏥 TRIAGE IA HOSPITAL")
        st.write("Clasificación clínica con login y base de datos real.")

        with st.form("triage_form"):
            st.subheader("1. Datos del paciente")
            col1, col2, col3 = st.columns(3)

            with col1:
                folio = st.text_input("Folio", value="P001")
                nombre_paciente = st.text_input("Nombre del paciente")
                edad = st.number_input("Edad", min_value=0, max_value=120, value=45)

            with col2:
                sexo = st.selectbox("Sexo", ["Femenino", "Masculino", "Otro"])
                motivo_consulta = st.text_input("Motivo principal de consulta")
                usuario_captura = st.text_input("Personal que realiza el triage", value=user["full_name"], disabled=True)

            with col3:
                fecha_hora_ingreso = st.text_input(
                    "Fecha y hora de ingreso",
                    value=datetime.now().strftime("%Y-%m-%d %H:%M")
                )

            st.subheader("2. Signos vitales")
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                frecuencia_cardiaca = st.number_input("Frecuencia cardiaca", 0, 300, 80)
                presion_sistolica = st.number_input("TA sistólica", 0, 300, 120)

            with c2:
                frecuencia_respiratoria = st.number_input("Frecuencia respiratoria", 0, 80, 18)
                presion_diastolica = st.number_input("TA diastólica", 0, 200, 80)

            with c3:
                temperatura = st.number_input("Temperatura °C", 30.0, 45.0, 36.5, step=0.1)
                saturacion_oxigeno = st.number_input("Saturación de oxígeno %", 0, 100, 98)

            with c4:
                glucosa_capilar = st.number_input("Glucosa capilar mg/dL", 0, 1000, 100)
                dolor_eva = st.slider("Dolor EVA", 0, 10, 0)
                estado_conciencia = st.selectbox(
                    "Estado de conciencia",
                    ["alerta", "somnoliento", "confuso", "inconsciente"]
                )

            st.subheader("3. Preguntas de alarma")
            p1, p2, p3, p4 = st.columns(4)

            with p1:
                dolor_toracico = st.checkbox("Dolor torácico")
                dificultad_respiratoria = st.checkbox("Dificultad respiratoria")
                fiebre = st.checkbox("Fiebre")
                sangrado_activo = st.checkbox("Sangrado activo")

            with p2:
                convulsiones = st.checkbox("Convulsiones")
                alteracion_mental = st.checkbox("Alteración mental")
                debilidad_unilateral = st.checkbox("Debilidad unilateral")
                alteracion_habla = st.checkbox("Alteración del habla")

            with p3:
                asimetria_facial = st.checkbox("Asimetría facial")
                inicio_subito = st.checkbox("Inicio súbito")
                sincope = st.checkbox("Síncope")
                palidez_diaforesis = st.checkbox("Palidez o diaforesis")

            with p4:
                trauma_reciente = st.checkbox("Trauma reciente")
                antecedente_hipertension = st.checkbox("Antecedente de hipertensión")
                antecedente_diabetes = st.checkbox("Antecedente de diabetes")
                puede_caminar = st.checkbox("Puede caminar por sí mismo", value=True)

            submitted = st.form_submit_button("Clasificar paciente")

        if submitted:
            data = TriageInput(
                folio=folio,
                nombre_paciente=nombre_paciente,
                edad=int(edad),
                sexo=sexo,
                motivo_consulta=motivo_consulta,
                usuario_captura=user["full_name"],
                rol_usuario=user["role"],
                fecha_hora_ingreso=fecha_hora_ingreso,
                frecuencia_cardiaca=int(frecuencia_cardiaca),
                frecuencia_respiratoria=int(frecuencia_respiratoria),
                presion_sistolica=int(presion_sistolica),
                presion_diastolica=int(presion_diastolica),
                temperatura=float(temperatura),
                saturacion_oxigeno=int(saturacion_oxigeno),
                glucosa_capilar=int(glucosa_capilar),
                dolor_eva=int(dolor_eva),
                estado_conciencia=estado_conciencia,
                dolor_toracico=bool(dolor_toracico),
                dificultad_respiratoria=bool(dificultad_respiratoria),
                fiebre=bool(fiebre),
                sangrado_activo=bool(sangrado_activo),
                convulsiones=bool(convulsiones),
                alteracion_mental=bool(alteracion_mental),
                debilidad_unilateral=bool(debilidad_unilateral),
                alteracion_habla=bool(alteracion_habla),
                asimetria_facial=bool(asimetria_facial),
                inicio_subito=bool(inicio_subito),
                sincope=bool(sincope),
                palidez_diaforesis=bool(palidez_diaforesis),
                trauma_reciente=bool(trauma_reciente),
                antecedente_hipertension=bool(antecedente_hipertension),
                antecedente_diabetes=bool(antecedente_diabetes),
                puede_caminar=bool(puede_caminar),
            )

            res = evaluar_triage(data)
            save_triage(data, res)

            st.subheader("Resultado del triage")

            if res["semaforo"] == "NARANJA":
                st.markdown(
                    f"""
                    <div class="orange-box">
                        <h2>🟠 {res["semaforo"]}</h2>
                        <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif res["semaforo"] == "AMARILLO":
                st.markdown(
                    f"""
                    <div class="yellow-box">
                        <h2>🟡 {res["semaforo"]}</h2>
                        <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="green-box">
                        <h2>🟢 {res["semaforo"]}</h2>
                        <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("**Motivos de clasificación**")
            for motivo in res["motivos"]:
                st.write(f"- {motivo}")

            st.markdown("**Alertas activadas**")
            if res["alertas"]:
                for alerta in res["alertas"]:
                    st.write(f"- {alerta}")
            else:
                st.write("- Sin alertas específicas")

            st.caption(res["aviso_legal"])
            st.success("Paciente guardado en la base de datos")

    with tab2:
        st.title("📊 Dashboard")
        df = load_triage_df()

        if df.empty:
            st.warning("No hay registros en la base de datos.")
        else:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")

            c1, c2, c3, c4 = st.columns(4)

            fecha_min = df["fecha_registro"].min().date()
            fecha_max = df["fecha_registro"].max().date()

            with c1:
                fecha_inicio = st.date_input("Fecha inicio", value=fecha_min)
            with c2:
                fecha_fin = st.date_input("Fecha fin", value=fecha_max)
            with c3:
                usuarios = ["Todos"] + sorted(df["usuario_captura"].dropna().astype(str).unique().tolist())
                usuario_filtro = st.selectbox("Usuario capturista", usuarios)
            with c4:
                semaforos = ["Todos", "NARANJA", "AMARILLO", "VERDE"]
                semaforo_filtro = st.selectbox("Semáforo", semaforos)

            filtrado = df[
                (df["fecha_registro"].dt.date >= fecha_inicio) &
                (df["fecha_registro"].dt.date <= fecha_fin)
            ]

            if usuario_filtro != "Todos":
                filtrado = filtrado[filtrado["usuario_captura"] == usuario_filtro]

            if semaforo_filtro != "Todos":
                filtrado = filtrado[filtrado["semaforo"] == semaforo_filtro]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total", int(len(filtrado)))
            m2.metric("🟠 Naranja", int((filtrado["semaforo"] == "NARANJA").sum()))
            m3.metric("🟡 Amarillo", int((filtrado["semaforo"] == "AMARILLO").sum()))
            m4.metric("🟢 Verde", int((filtrado["semaforo"] == "VERDE").sum()))

            if not filtrado.empty:
                st.bar_chart(filtrado["semaforo"].value_counts())
                st.dataframe(filtrado, use_container_width=True)
            else:
                st.info("No hay registros con esos filtros.")

    with tab3:
        st.title("👥 Usuarios")
        users_df = load_users_df()
        st.dataframe(users_df, use_container_width=True)