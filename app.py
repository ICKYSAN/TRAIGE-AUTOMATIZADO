
import io
import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

DB_FILE = "triage_hospital.db"

st.set_page_config(page_title="TRIAGE AUTOMATIZADO CON IA V5", page_icon="🏥", layout="wide")

st.markdown("""
<style>
.orange-box {background-color: #fff7ed; border-left: 8px solid #f97316; padding: 1rem; border-radius: 0.8rem;}
.yellow-box {background-color: #fefce8; border-left: 8px solid #eab308; padding: 1rem; border-radius: 0.8rem;}
.green-box {background-color: #f0fdf4; border-left: 8px solid #22c55e; padding: 1rem; border-radius: 0.8rem;}
.danger-box {background-color: #fef2f2; border-left: 8px solid #dc2626; padding: 1rem; border-radius: 0.8rem;}
.pill-orange {background:#f97316;color:white;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
.pill-yellow {background:#eab308;color:black;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
.pill-green {background:#22c55e;color:white;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
.pill-red {background:#dc2626;color:white;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
</style>
""", unsafe_allow_html=True)

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
    modulo: str
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
    embarazo: bool
    semanas_gestacion: int
    sangrado_vaginal: bool
    dolor_pelvico: bool
    hipertension_embarazo: bool
    cefalea_intensa: bool
    vision_borrosa: bool
    movimientos_fetales_disminuidos: bool
    sepsis_score: int = 0
    sepsis_alerta: str = ""

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

def authenticate_user(username: str, password: str) -> Optional[dict]:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, role, salt, password_hash, is_active FROM users WHERE username = ?", (username,))
    row = cur.fetchone(); conn.close()
    if not row:
        return None
    user = {"id": row[0], "username": row[1], "full_name": row[2], "role": row[3], "salt": row[4], "password_hash": row[5], "is_active": row[6]}
    if user["is_active"] != 1:
        return None
    return user if hash_password(password, user["salt"]) == user["password_hash"] else None

def create_user(username: str, full_name: str, role: str, password: str):
    conn = get_conn(); cur = conn.cursor()
    salt = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()[:32]
    password_hash = hash_password(password, salt)
    cur.execute("INSERT INTO users (username, full_name, role, salt, password_hash) VALUES (?, ?, ?, ?, ?)", (username, full_name, role, salt, password_hash))
    conn.commit(); conn.close()

def update_user(user_id: int, full_name: str, role: str, is_active: int):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?", (full_name, role, is_active, user_id))
    conn.commit(); conn.close()

def load_users_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id DESC", conn)
    conn.close()
    return df

def get_shift_from_dt(dt_value) -> str:
    dt = pd.to_datetime(dt_value, errors="coerce")
    if pd.isna(dt):
        return "Desconocido"
    hour = dt.hour
    if 7 <= hour < 14:
        return "Matutino"
    if 14 <= hour < 21:
        return "Vespertino"
    return "Nocturno"

def calculate_wait_minutes(fecha_registro_value) -> Optional[int]:
    dt = pd.to_datetime(fecha_registro_value, errors="coerce")
    if pd.isna(dt):
        return None
    return max(int((datetime.now() - dt.to_pydatetime()).total_seconds() // 60), 0)

def format_wait(wait_minutes: Optional[int]) -> str:
    if wait_minutes is None:
        return "-"
    return f"{wait_minutes // 60:02d}:{wait_minutes % 60:02d}"

def expected_reassessment_minutes(semaforo: str) -> int:
    return 0 if semaforo == "NARANJA" else 30 if semaforo == "AMARILLO" else 60

def color_badge(semaforo: str) -> str:
    if semaforo == "NARANJA":
        return '<span class="pill-orange">NARANJA</span>'
    if semaforo == "AMARILLO":
        return '<span class="pill-yellow">AMARILLO</span>'
    return '<span class="pill-green">VERDE</span>'

def alert_badge(exceeded: bool) -> str:
    return '<span class="pill-red">TIEMPO EXCEDIDO</span>' if exceeded else '<span class="pill-green">EN TIEMPO</span>'

def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Triage")
    return output.getvalue()

def build_printable_html(record: pd.Series) -> str:
    return f"""
    <html><body style='font-family:Arial;margin:24px;'>
    <button onclick='window.print()'>Imprimir hoja de triage</button>
    <h1>Hoja de Triage</h1>
    <p><b>Folio:</b> {record.get('folio','')}</p>
    <p><b>Nombre:</b> {record.get('nombre_paciente','')}</p>
    <p><b>Módulo:</b> {record.get('modulo','')}</p>
    <p><b>Semáforo:</b> {record.get('semaforo','')}</p>
    <p><b>Acción sugerida:</b> {record.get('accion_sugerida','')}</p>
    <p><b>Motivos:</b> {record.get('motivos','')}</p>
    <p><b>Alertas:</b> {record.get('alertas','')}</p>
    <p><b>Sepsis score:</b> {record.get('sepsis_score','')}</p>
    </body></html>
    """

def compute_sepsis_score(data: TriageInput) -> Tuple[int, str]:
    score = 0
    if data.temperatura > 38 or data.temperatura < 36: score += 1
    if data.frecuencia_cardiaca > 90: score += 1
    if data.frecuencia_respiratoria > 22: score += 1
    if data.presion_sistolica < 100: score += 1
    if data.alteracion_mental or data.estado_conciencia in ["somnoliento", "confuso", "inconsciente"]: score += 1
    if score >= 4: return score, "Alto riesgo de sepsis"
    if score >= 2: return score, "Riesgo intermedio de sepsis"
    return score, "Riesgo bajo de sepsis"

def resultado(semaforo: str, accion: str, motivos: List[str], alertas: List[str], data: TriageInput) -> Dict[str, Any]:
    return {
        "folio": data.folio,
        "nombre_paciente": data.nombre_paciente,
        "semaforo": semaforo,
        "accion_sugerida": accion,
        "motivos": motivos,
        "alertas": alertas,
        "datos_capturados": asdict(data),
        "sepsis_score": data.sepsis_score,
        "sepsis_alerta": data.sepsis_alerta,
        "aviso_legal": "Herramienta de apoyo para priorización clínica. El score de sepsis es orientativo y no sustituye la valoración médica ni el juicio clínico."
    }

def evaluar_triage(data: TriageInput) -> Dict[str, Any]:
    alertas: List[str] = []
    motivos: List[str] = []
    data.sepsis_score, data.sepsis_alerta = compute_sepsis_score(data)
    if data.sepsis_score >= 2:
        alertas.append(f"Sepsis score: {data.sepsis_score} ({data.sepsis_alerta})")
    estado = data.estado_conciencia.strip().lower()

    if data.modulo == "Obstétrico":
        motivos.append("Módulo obstétrico activado")
        if data.sangrado_vaginal or (data.hipertension_embarazo and (data.cefalea_intensa or data.vision_borrosa)):
            return resultado("NARANJA", "Valoración obstétrica inmediata", motivos + ["Alerta obstétrica"], alertas + ["Alerta obstétrica"], data)
        if data.dolor_pelvico or data.movimientos_fetales_disminuidos:
            return resultado("AMARILLO", "Valoración obstétrica prioritaria", motivos + ["Vigilancia obstétrica"], alertas + ["Vigilancia obstétrica"], data)

    if estado == "inconsciente":
        return resultado("NARANJA", "Valoración médica inmediata", motivos + ["Paciente inconsciente"], alertas, data)
    if data.convulsiones:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + ["Convulsiones activas o recientes"], alertas, data)
    if data.saturacion_oxigeno < 90:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + [f"Saturación crítica: {data.saturacion_oxigeno}%"], alertas + ["Compromiso respiratorio"], data)
    if data.presion_sistolica < 90:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + [f"Hipotensión: {data.presion_sistolica} mmHg"], alertas, data)
    if data.sangrado_activo:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + ["Sangrado activo"], alertas, data)
    if data.dificultad_respiratoria and data.saturacion_oxigeno < 90:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + ["Dificultad respiratoria con desaturación"], alertas + ["Compromiso respiratorio"], data)
    if data.frecuencia_respiratoria > 30:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + [f"Taquipnea severa: {data.frecuencia_respiratoria}"], alertas + ["Compromiso respiratorio"], data)
    if data.inicio_subito and (data.alteracion_habla or data.debilidad_unilateral or data.asimetria_facial):
        return resultado("NARANJA", "Activar protocolo neurológico / valoración inmediata", motivos + ["Déficit neurológico súbito"], alertas + ["Código Cerebro"], data)
    if data.dolor_toracico and data.palidez_diaforesis and (data.presion_sistolica < 90 or data.saturacion_oxigeno < 94):
        return resultado("NARANJA", "Activar protocolo cardiovascular / valoración inmediata", motivos + ["Dolor torácico con datos de alto riesgo"], alertas + ["Código Infarto"], data)
    if estado == "confuso" and not data.puede_caminar:
        return resultado("NARANJA", "Valoración médica inmediata", motivos + ["Confusión con incapacidad funcional"], alertas, data)
    if data.sepsis_score >= 4:
        return resultado("NARANJA", "Valoración inmediata por sospecha de sepsis", motivos + [f"Sepsis score alto: {data.sepsis_score}"], alertas + ["Código Sepsis"], data)
    if data.sepsis_score >= 2:
        return resultado("AMARILLO", "Valoración prioritaria por sospecha de sepsis", motivos + [f"Sepsis score intermedio: {data.sepsis_score}"], alertas + ["Código Sepsis"], data)
    if 90 <= data.saturacion_oxigeno <= 93:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + [f"Saturación limítrofe: {data.saturacion_oxigeno}%"], alertas, data)
    if data.frecuencia_cardiaca > 120:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + [f"Taquicardia: {data.frecuencia_cardiaca}"], alertas, data)
    if data.frecuencia_respiratoria > 22:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + [f"Taquipnea: {data.frecuencia_respiratoria}"], alertas, data)
    if estado in ["somnoliento", "confuso"] or data.alteracion_mental:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + ["Alteración del estado mental no crítica"], alertas, data)
    if data.dolor_toracico:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + ["Dolor torácico sin criterios de máxima prioridad"], alertas, data)
    if data.dificultad_respiratoria:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + ["Dificultad respiratoria leve a moderada"], alertas + ["Compromiso respiratorio"], data)
    if data.dolor_eva >= 5:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + [f"Dolor EVA {data.dolor_eva}/10"], alertas, data)
    if data.fiebre:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + ["Fiebre"], alertas, data)
    if data.trauma_reciente:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + ["Trauma reciente con estabilidad"], alertas, data)
    if data.glucosa_capilar < 70 or data.glucosa_capilar > 250:
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos + [f"Glucosa alterada: {data.glucosa_capilar}"], alertas, data)
    return resultado("VERDE", "Atención diferida", motivos + ["Paciente estable, sin datos de alarma mayores"], alertas, data)

def save_triage(data: TriageInput, res: Dict[str, Any], tipo_registro: str = "Inicial"):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO triage_records (
            fecha_registro, tipo_registro, folio, nombre_paciente, edad, sexo, motivo_consulta,
            usuario_captura, rol_usuario, fecha_hora_ingreso, modulo,
            frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
            temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
            dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
            alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
            inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
            antecedente_hipertension, antecedente_diabetes, puede_caminar,
            embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo,
            cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos,
            sepsis_score, sepsis_alerta,
            semaforo, accion_sugerida, motivos, alertas, estado_operativo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tipo_registro, data.folio, data.nombre_paciente, data.edad, data.sexo, data.motivo_consulta,
        data.usuario_captura, data.rol_usuario, data.fecha_hora_ingreso, data.modulo,
        data.frecuencia_cardiaca, data.frecuencia_respiratoria, data.presion_sistolica, data.presion_diastolica,
        data.temperatura, data.saturacion_oxigeno, data.glucosa_capilar, data.dolor_eva, data.estado_conciencia,
        int(data.dolor_toracico), int(data.dificultad_respiratoria), int(data.fiebre), int(data.sangrado_activo), int(data.convulsiones),
        int(data.alteracion_mental), int(data.debilidad_unilateral), int(data.alteracion_habla), int(data.asimetria_facial),
        int(data.inicio_subito), int(data.sincope), int(data.palidez_diaforesis), int(data.trauma_reciente),
        int(data.antecedente_hipertension), int(data.antecedente_diabetes), int(data.puede_caminar),
        int(data.embarazo), data.semanas_gestacion, int(data.sangrado_vaginal), int(data.dolor_pelvico), int(data.hipertension_embarazo),
        int(data.cefalea_intensa), int(data.vision_borrosa), int(data.movimientos_fetales_disminuidos),
        data.sepsis_score, data.sepsis_alerta,
        res["semaforo"], res["accion_sugerida"], " | ".join(res["motivos"]), " | ".join(res["alertas"]) if res["alertas"] else "", "Pendiente"
    ))
    conn.commit(); conn.close()

def load_triage_df() -> pd.DataFrame:
    conn = get_conn(); df = pd.read_sql_query("SELECT * FROM triage_records ORDER BY id DESC", conn); conn.close(); return df

def load_operational_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""SELECT id, fecha_registro, tipo_registro, folio, nombre_paciente, modulo, semaforo, accion_sugerida, usuario_captura, rol_usuario, estado_operativo, motivos, alertas FROM triage_records ORDER BY datetime(fecha_registro) DESC, id DESC""", conn)
    conn.close()
    return df

def get_latest_patient_by_folio(folio: str) -> Optional[dict]:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        SELECT folio, nombre_paciente, edad, sexo, motivo_consulta, fecha_hora_ingreso, modulo,
               frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
               temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
               dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
               alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
               inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
               antecedente_hipertension, antecedente_diabetes, puede_caminar,
               embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo,
               cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos
        FROM triage_records WHERE folio = ? ORDER BY id DESC LIMIT 1
    """, (folio,))
    row = cur.fetchone(); conn.close()
    if not row:
        return None
    keys = ["folio","nombre_paciente","edad","sexo","motivo_consulta","fecha_hora_ingreso","modulo","frecuencia_cardiaca","frecuencia_respiratoria","presion_sistolica","presion_diastolica","temperatura","saturacion_oxigeno","glucosa_capilar","dolor_eva","estado_conciencia","dolor_toracico","dificultad_respiratoria","fiebre","sangrado_activo","convulsiones","alteracion_mental","debilidad_unilateral","alteracion_habla","asimetria_facial","inicio_subito","sincope","palidez_diaforesis","trauma_reciente","antecedente_hipertension","antecedente_diabetes","puede_caminar","embarazo","semanas_gestacion","sangrado_vaginal","dolor_pelvico","hipertension_embarazo","cefalea_intensa","vision_borrosa","movimientos_fetales_disminuidos"]
    patient = dict(zip(keys, row))
    for f in ["dolor_toracico","dificultad_respiratoria","fiebre","sangrado_activo","convulsiones","alteracion_mental","debilidad_unilateral","alteracion_habla","asimetria_facial","inicio_subito","sincope","palidez_diaforesis","trauma_reciente","antecedente_hipertension","antecedente_diabetes","puede_caminar","embarazo","sangrado_vaginal","dolor_pelvico","hipertension_embarazo","cefalea_intensa","vision_borrosa","movimientos_fetales_disminuidos"]:
        patient[f] = bool(patient[f])
    return patient

def update_operational_status(record_id: int, estado_operativo: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE triage_records SET estado_operativo = ? WHERE id = ?", (estado_operativo, record_id))
    conn.commit(); conn.close()

def build_triage_input(*args):
    return TriageInput(*args)

def render_obstetric_fields(prefix: str, defaults: Optional[dict] = None):
    defaults = defaults or {}
    st.subheader("Módulo obstétrico")
    c1, c2, c3 = st.columns(3)
    with c1:
        embarazo = st.checkbox("Embarazo", value=defaults.get("embarazo", False), key=f"{prefix}_embarazo")
        semanas_gestacion = st.number_input("Semanas de gestación", 0, 45, int(defaults.get("semanas_gestacion", 0)), key=f"{prefix}_semanas")
        sangrado_vaginal = st.checkbox("Sangrado vaginal", value=defaults.get("sangrado_vaginal", False), key=f"{prefix}_sv")
    with c2:
        dolor_pelvico = st.checkbox("Dolor pélvico", value=defaults.get("dolor_pelvico", False), key=f"{prefix}_dp")
        hipertension_embarazo = st.checkbox("Hipertensión en embarazo", value=defaults.get("hipertension_embarazo", False), key=f"{prefix}_he")
        cefalea_intensa = st.checkbox("Cefalea intensa", value=defaults.get("cefalea_intensa", False), key=f"{prefix}_cef")
    with c3:
        vision_borrosa = st.checkbox("Visión borrosa", value=defaults.get("vision_borrosa", False), key=f"{prefix}_vb")
        movimientos_fetales_disminuidos = st.checkbox("Movimientos fetales disminuidos", value=defaults.get("movimientos_fetales_disminuidos", False), key=f"{prefix}_mfd")
    return embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo, cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    st.title("🔐 Login - TRIAGE IA HOSPITAL V5")
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
else:
    user = st.session_state.user
    st.sidebar.success(f"Sesión activa: {user['full_name']}")
    st.sidebar.write(f"Rol: {user['role']}")
    if st.sidebar.button("Cerrar sesión"):
        logout()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Triage Inicial", "Revaloración", "Bandeja Operativa", "Dashboard", "Usuarios"])

    with tab1:
        st.title("🏥 TRIAGE INICIAL")
        modulo = st.radio("Selecciona módulo", ["General", "Obstétrico"], horizontal=True)
        with st.form("triage_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                folio = st.text_input("Folio", value="P001")
                nombre_paciente = st.text_input("Nombre del paciente")
                edad = st.number_input("Edad", min_value=0, max_value=120, value=45)
            with col2:
                sexo = st.selectbox("Sexo", ["Femenino", "Masculino", "Otro"])
                motivo_consulta = st.text_input("Motivo principal de consulta")
                st.text_input("Personal que realiza el triage", value=user["full_name"], disabled=True)
            with col3:
                fecha_hora_ingreso = st.text_input("Fecha y hora de ingreso", value=datetime.now().strftime("%Y-%m-%d %H:%M"))

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                frecuencia_cardiaca = st.number_input("Frecuencia cardiaca", 0, 300, 80, key="ini_fc")
                presion_sistolica = st.number_input("TA sistólica", 0, 300, 120, key="ini_pas")
            with c2:
                frecuencia_respiratoria = st.number_input("Frecuencia respiratoria", 0, 80, 18, key="ini_fr")
                presion_diastolica = st.number_input("TA diastólica", 0, 200, 80, key="ini_pad")
            with c3:
                temperatura = st.number_input("Temperatura °C", 30.0, 45.0, 36.5, step=0.1, key="ini_temp")
                saturacion_oxigeno = st.number_input("Saturación de oxígeno %", 0, 100, 98, key="ini_spo2")
            with c4:
                glucosa_capilar = st.number_input("Glucosa capilar mg/dL", 0, 1000, 100, key="ini_glu")
                dolor_eva = st.slider("Dolor EVA", 0, 10, 0, key="ini_dolor")
                estado_conciencia = st.selectbox("Estado de conciencia", ["alerta", "somnoliento", "confuso", "inconsciente"], key="ini_estado")

            p1, p2, p3, p4 = st.columns(4)
            with p1:
                dolor_toracico = st.checkbox("Dolor torácico", key="ini_dt")
                dificultad_respiratoria = st.checkbox("Dificultad respiratoria", key="ini_dr")
                fiebre = st.checkbox("Fiebre", key="ini_fiebre")
                sangrado_activo = st.checkbox("Sangrado activo", key="ini_sangrado")
            with p2:
                convulsiones = st.checkbox("Convulsiones", key="ini_conv")
                alteracion_mental = st.checkbox("Alteración mental", key="ini_altm")
                debilidad_unilateral = st.checkbox("Debilidad unilateral", key="ini_deb")
                alteracion_habla = st.checkbox("Alteración del habla", key="ini_habla")
            with p3:
                asimetria_facial = st.checkbox("Asimetría facial", key="ini_cara")
                inicio_subito = st.checkbox("Inicio súbito", key="ini_inicio")
                sincope = st.checkbox("Síncope", key="ini_sincope")
                palidez_diaforesis = st.checkbox("Palidez o diaforesis", key="ini_palidez")
            with p4:
                trauma_reciente = st.checkbox("Trauma reciente", key="ini_trauma")
                antecedente_hipertension = st.checkbox("Antecedente de hipertensión", key="ini_hta")
                antecedente_diabetes = st.checkbox("Antecedente de diabetes", key="ini_dm")
                puede_caminar = st.checkbox("Puede caminar por sí mismo", value=True, key="ini_camina")

            if modulo == "Obstétrico":
                embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo, cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos = render_obstetric_fields("ini")
            else:
                embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo, cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos = (False, 0, False, False, False, False, False, False)

            submitted = st.form_submit_button("Clasificar paciente")

        if submitted:
            data = TriageInput(
                folio, nombre_paciente, int(edad), sexo, motivo_consulta, user["full_name"], user["role"], fecha_hora_ingreso, modulo,
                int(frecuencia_cardiaca), int(frecuencia_respiratoria), int(presion_sistolica), int(presion_diastolica),
                float(temperatura), int(saturacion_oxigeno), int(glucosa_capilar), int(dolor_eva), estado_conciencia,
                bool(dolor_toracico), bool(dificultad_respiratoria), bool(fiebre), bool(sangrado_activo), bool(convulsiones),
                bool(alteracion_mental), bool(debilidad_unilateral), bool(alteracion_habla), bool(asimetria_facial),
                bool(inicio_subito), bool(sincope), bool(palidez_diaforesis), bool(trauma_reciente),
                bool(antecedente_hipertension), bool(antecedente_diabetes), bool(puede_caminar),
                bool(embarazo), int(semanas_gestacion), bool(sangrado_vaginal), bool(dolor_pelvico),
                bool(hipertension_embarazo), bool(cefalea_intensa), bool(vision_borrosa), bool(movimientos_fetales_disminuidos)
            )
            res = evaluar_triage(data)
            save_triage(data, res, "Inicial")
            st.success(f"Paciente guardado. Sepsis score: {res['sepsis_score']} - {res['sepsis_alerta']}")
            st.write(f"Semáforo: {res['semaforo']} | Acción: {res['accion_sugerida']}")
            st.write("Motivos:", " | ".join(res["motivos"]))
            st.write("Alertas:", " | ".join(res["alertas"]) if res["alertas"] else "Sin alertas")

    with tab2:
        st.title("🔁 REVALORACIÓN DEL PACIENTE")
        folio_reval = st.text_input("Buscar folio para revaloración")
        patient = get_latest_patient_by_folio(folio_reval.strip()) if folio_reval.strip() else None
        if folio_reval.strip() and not patient:
            st.warning("No se encontró ese folio")
        if patient:
            st.success("Paciente encontrado")
            modulo_rv = st.radio("Módulo de revaloración", ["General", "Obstétrico"], horizontal=True, index=0 if patient.get("modulo", "General") == "General" else 1)
            with st.form("revaloracion_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.text_input("Folio", value=patient["folio"], disabled=True)
                    rv_nombre = st.text_input("Nombre", value=patient["nombre_paciente"])
                    rv_edad = st.number_input("Edad", min_value=0, max_value=120, value=int(patient["edad"]))
                with col2:
                    sexos = ["Femenino", "Masculino", "Otro"]
                    rv_sexo = st.selectbox("Sexo", sexos, index=sexos.index(patient["sexo"]) if patient["sexo"] in sexos else 0)
                    rv_motivo = st.text_input("Motivo de consulta", value=patient["motivo_consulta"])
                    st.text_input("Revalorado por", value=user["full_name"], disabled=True)
                with col3:
                    rv_fecha_hora_ingreso = st.text_input("Fecha y hora de ingreso", value=patient["fecha_hora_ingreso"])

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    rv_fc = st.number_input("Frecuencia cardiaca", 0, 300, int(patient["frecuencia_cardiaca"]), key="rv_fc")
                    rv_pas = st.number_input("TA sistólica", 0, 300, int(patient["presion_sistolica"]), key="rv_pas")
                with c2:
                    rv_fr = st.number_input("Frecuencia respiratoria", 0, 80, int(patient["frecuencia_respiratoria"]), key="rv_fr")
                    rv_pad = st.number_input("TA diastólica", 0, 200, int(patient["presion_diastolica"]), key="rv_pad")
                with c3:
                    rv_temp = st.number_input("Temperatura °C", 30.0, 45.0, float(patient["temperatura"]), step=0.1, key="rv_temp")
                    rv_spo2 = st.number_input("Saturación de oxígeno %", 0, 100, int(patient["saturacion_oxigeno"]), key="rv_spo2")
                with c4:
                    rv_glu = st.number_input("Glucosa capilar mg/dL", 0, 1000, int(patient["glucosa_capilar"]), key="rv_glu")
                    rv_dolor = st.slider("Dolor EVA", 0, 10, int(patient["dolor_eva"]), key="rv_dolor")
                    estados = ["alerta", "somnoliento", "confuso", "inconsciente"]
                    rv_estado = st.selectbox("Estado de conciencia", estados, index=estados.index(patient["estado_conciencia"]) if patient["estado_conciencia"] in estados else 0)

                p1, p2, p3, p4 = st.columns(4)
                with p1:
                    rv_dt = st.checkbox("Dolor torácico", value=patient["dolor_toracico"], key="rv_dt")
                    rv_dr = st.checkbox("Dificultad respiratoria", value=patient["dificultad_respiratoria"], key="rv_dr")
                    rv_fiebre = st.checkbox("Fiebre", value=patient["fiebre"], key="rv_fiebre")
                    rv_sangrado = st.checkbox("Sangrado activo", value=patient["sangrado_activo"], key="rv_sangrado")
                with p2:
                    rv_conv = st.checkbox("Convulsiones", value=patient["convulsiones"], key="rv_conv")
                    rv_altm = st.checkbox("Alteración mental", value=patient["alteracion_mental"], key="rv_altm")
                    rv_deb = st.checkbox("Debilidad unilateral", value=patient["debilidad_unilateral"], key="rv_deb")
                    rv_habla = st.checkbox("Alteración del habla", value=patient["alteracion_habla"], key="rv_habla")
                with p3:
                    rv_cara = st.checkbox("Asimetría facial", value=patient["asimetria_facial"], key="rv_cara")
                    rv_inicio = st.checkbox("Inicio súbito", value=patient["inicio_subito"], key="rv_inicio")
                    rv_sincope = st.checkbox("Síncope", value=patient["sincope"], key="rv_sincope")
                    rv_palidez = st.checkbox("Palidez o diaforesis", value=patient["palidez_diaforesis"], key="rv_palidez")
                with p4:
                    rv_trauma = st.checkbox("Trauma reciente", value=patient["trauma_reciente"], key="rv_trauma")
                    rv_hta = st.checkbox("Antecedente de hipertensión", value=patient["antecedente_hipertension"], key="rv_hta")
                    rv_dm = st.checkbox("Antecedente de diabetes", value=patient["antecedente_diabetes"], key="rv_dm")
                    rv_camina = st.checkbox("Puede caminar por sí mismo", value=patient["puede_caminar"], key="rv_camina")

                if modulo_rv == "Obstétrico":
                    rv_embarazo, rv_semanas, rv_sv, rv_dp, rv_he, rv_cef, rv_vb, rv_mfd = render_obstetric_fields("rv", patient)
                else:
                    rv_embarazo, rv_semanas, rv_sv, rv_dp, rv_he, rv_cef, rv_vb, rv_mfd = (patient["embarazo"], patient["semanas_gestacion"], patient["sangrado_vaginal"], patient["dolor_pelvico"], patient["hipertension_embarazo"], patient["cefalea_intensa"], patient["vision_borrosa"], patient["movimientos_fetales_disminuidos"])

                rv_submit = st.form_submit_button("Guardar revaloración")

            if rv_submit:
                rv_data = TriageInput(
                    patient["folio"], rv_nombre, int(rv_edad), rv_sexo, rv_motivo, user["full_name"], user["role"], rv_fecha_hora_ingreso, modulo_rv,
                    int(rv_fc), int(rv_fr), int(rv_pas), int(rv_pad), float(rv_temp), int(rv_spo2), int(rv_glu), int(rv_dolor), rv_estado,
                    bool(rv_dt), bool(rv_dr), bool(rv_fiebre), bool(rv_sangrado), bool(rv_conv), bool(rv_altm), bool(rv_deb), bool(rv_habla),
                    bool(rv_cara), bool(rv_inicio), bool(rv_sincope), bool(rv_palidez), bool(rv_trauma), bool(rv_hta), bool(rv_dm), bool(rv_camina),
                    bool(rv_embarazo), int(rv_semanas), bool(rv_sv), bool(rv_dp), bool(rv_he), bool(rv_cef), bool(rv_vb), bool(rv_mfd)
                )
                rv_res = evaluar_triage(rv_data)
                save_triage(rv_data, rv_res, "Revaloración")
                st.success(f"Revaloración guardada. Sepsis score: {rv_res['sepsis_score']} - {rv_res['sepsis_alerta']}")
                st.write(f"Semáforo: {rv_res['semaforo']} | Acción: {rv_res['accion_sugerida']}")

    with tab3:
        st.title("🧭 BANDEJA OPERATIVA")
        oper_df = load_operational_df()
        if oper_df.empty:
            st.warning("No hay registros operativos.")
        else:
            oper_df["fecha_registro"] = pd.to_datetime(oper_df["fecha_registro"], errors="coerce")
            oper_df["minutos_espera"] = oper_df["fecha_registro"].apply(calculate_wait_minutes)
            oper_df["cronometro"] = oper_df["minutos_espera"].apply(format_wait)
            oper_df["meta_revaloracion_min"] = oper_df["semaforo"].apply(expected_reassessment_minutes)
            oper_df["tiempo_excedido"] = oper_df.apply(lambda row: bool(row["meta_revaloracion_min"] > 0 and row["minutos_espera"] is not None and row["minutos_espera"] > row["meta_revaloracion_min"]), axis=1)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                semaforo_oper = st.selectbox("Filtrar por semáforo", ["Todos", "NARANJA", "AMARILLO", "VERDE"])
            with col2:
                estado_oper = st.selectbox("Filtrar por estado", ["Todos", "Pendiente", "Atendido", "Revaloración"])
            with col3:
                folio_oper = st.text_input("Buscar folio")
            with col4:
                solo_excedidos = st.checkbox("Solo tiempos excedidos")

            oper_filtrado = oper_df.copy()
            if semaforo_oper != "Todos":
                oper_filtrado = oper_filtrado[oper_filtrado["semaforo"] == semaforo_oper]
            if estado_oper != "Todos":
                oper_filtrado = oper_filtrado[oper_filtrado["estado_operativo"] == estado_oper]
            if folio_oper.strip():
                oper_filtrado = oper_filtrado[oper_filtrado["folio"].astype(str).str.contains(folio_oper.strip(), case=False, na=False)]
            if solo_excedidos:
                oper_filtrado = oper_filtrado[oper_filtrado["tiempo_excedido"] == True]

            for _, row in oper_filtrado.head(25).iterrows():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1.8, 1.2, 1.0, 1.2, 1.2, 2.0])
                with c1: st.markdown(color_badge(row["semaforo"]), unsafe_allow_html=True)
                with c2:
                    st.write(f"**{row['folio']}**")
                    st.caption(str(row["nombre_paciente"]))
                with c3: st.write(row["modulo"])
                with c4: st.write(row["cronometro"])
                with c5: st.write(f"Meta {row['meta_revaloracion_min']} min")
                with c6: st.write(row["estado_operativo"])
                with c7: st.markdown(alert_badge(bool(row["tiempo_excedido"])), unsafe_allow_html=True)

            if oper_filtrado["tiempo_excedido"].any():
                st.markdown(f"""<div class="danger-box"><strong>Alerta:</strong> {int(oper_filtrado["tiempo_excedido"].sum())} registros superan el tiempo objetivo.</div>""", unsafe_allow_html=True)

            st.dataframe(oper_filtrado[["id","fecha_registro","tipo_registro","folio","nombre_paciente","modulo","semaforo","estado_operativo","usuario_captura","cronometro","meta_revaloracion_min","tiempo_excedido","accion_sugerida"]], use_container_width=True)

            ids_disponibles = oper_filtrado["id"].tolist()
            if ids_disponibles:
                c1, c2 = st.columns(2)
                with c1: selected_id = st.selectbox("Selecciona ID de registro", ids_disponibles)
                with c2: nuevo_estado = st.selectbox("Nuevo estado", ["Pendiente", "Atendido", "Revaloración"])
                if st.button("Actualizar estado operativo"):
                    update_operational_status(int(selected_id), nuevo_estado)
                    st.success("Estado actualizado")
                    st.rerun()

    with tab4:
        st.title("📊 DASHBOARD")
        df = load_triage_df()
        if df.empty:
            st.warning("No hay registros en la base de datos.")
        else:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df["minutos_espera"] = df["fecha_registro"].apply(calculate_wait_minutes)
            df["turno"] = df["fecha_registro"].apply(get_shift_from_dt)

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            fecha_min = df["fecha_registro"].min().date()
            fecha_max = df["fecha_registro"].max().date()
            with c1: fecha_inicio = st.date_input("Fecha inicio", value=fecha_min)
            with c2: fecha_fin = st.date_input("Fecha fin", value=fecha_max)
            with c3:
                usuarios = ["Todos"] + sorted(df["usuario_captura"].dropna().astype(str).unique().tolist())
                usuario_filtro = st.selectbox("Usuario capturista", usuarios)
            with c4:
                turno_filtro = st.selectbox("Turno", ["Todos", "Matutino", "Vespertino", "Nocturno"])
            with c5:
                semaforo_filtro = st.selectbox("Semáforo", ["Todos", "NARANJA", "AMARILLO", "VERDE"])
            with c6:
                modulo_filtro = st.selectbox("Módulo", ["Todos", "General", "Obstétrico"])

            s1, s2 = st.columns(2)
            with s1: folio_filtro = st.text_input("Buscar por folio")
            with s2: nombre_filtro = st.text_input("Buscar por nombre")

            filtrado = df[(df["fecha_registro"].dt.date >= fecha_inicio) & (df["fecha_registro"].dt.date <= fecha_fin)]
            if usuario_filtro != "Todos": filtrado = filtrado[filtrado["usuario_captura"] == usuario_filtro]
            if turno_filtro != "Todos": filtrado = filtrado[filtrado["turno"] == turno_filtro]
            if semaforo_filtro != "Todos": filtrado = filtrado[filtrado["semaforo"] == semaforo_filtro]
            if modulo_filtro != "Todos": filtrado = filtrado[filtrado["modulo"] == modulo_filtro]
            if folio_filtro.strip(): filtrado = filtrado[filtrado["folio"].astype(str).str.contains(folio_filtro.strip(), case=False, na=False)]
            if nombre_filtro.strip(): filtrado = filtrado[filtrado["nombre_paciente"].astype(str).str.contains(nombre_filtro.strip(), case=False, na=False)]

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Total", int(len(filtrado)))
            m2.metric("🟠 Naranja", int((filtrado["semaforo"] == "NARANJA").sum()))
            m3.metric("🟡 Amarillo", int((filtrado["semaforo"] == "AMARILLO").sum()))
            m4.metric("🟢 Verde", int((filtrado["semaforo"] == "VERDE").sum()))
            m5.metric("🔁 Revaloraciones", int((filtrado["tipo_registro"] == "Revaloración").sum()))
            m6.metric("⏱ Espera prom. min", round(float(filtrado["minutos_espera"].dropna().mean()), 1) if not filtrado.empty else 0)

            if not filtrado.empty:
                st.bar_chart(filtrado["semaforo"].value_counts())
                st.subheader("Indicadores por turno")
                st.bar_chart(filtrado.groupby("turno").size().rename("total"))
                st.subheader("Indicadores por usuario")
                st.bar_chart(filtrado.groupby("usuario_captura").size().rename("total").sort_values(ascending=False))
                st.subheader("Cruce turno por usuario")
                st.dataframe(filtrado.pivot_table(index="usuario_captura", columns="turno", values="id", aggfunc="count", fill_value=0), use_container_width=True)
                st.subheader("Promedio de sepsis score por usuario")
                sepsis_user = filtrado.groupby("usuario_captura")["sepsis_score"].mean().round(2).sort_values(ascending=False)
                st.dataframe(sepsis_user.reset_index(name="promedio_sepsis_score"), use_container_width=True)
                st.dataframe(filtrado, use_container_width=True)

                st.download_button("Descargar resultados filtrados en CSV", data=filtrado.to_csv(index=False).encode("utf-8"), file_name="triage_filtrado_v5.csv", mime="text/csv")
                st.download_button("Descargar resultados filtrados en Excel", data=dataframe_to_excel_bytes(filtrado), file_name="triage_filtrado_v5.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                opciones_impresion = filtrado.apply(lambda row: f"{row['id']} - {row['folio']} - {row['nombre_paciente']}", axis=1).tolist()
                selected_print = st.selectbox("Selecciona registro para imprimir", opciones_impresion)
                selected_print_id = int(selected_print.split(" - ")[0])
                selected_record = filtrado[filtrado["id"] == selected_print_id].iloc[0]
                st.download_button("Descargar hoja de triage en HTML", data=build_printable_html(selected_record).encode("utf-8"), file_name=f"hoja_triage_{selected_record['folio']}.html", mime="text/html")

    with tab5:
        if user["role"] != "Administrador":
            st.warning("Solo el Administrador puede gestionar usuarios.")
        else:
            st.title("👥 GESTIÓN DE USUARIOS")
            users_df = load_users_df()
            st.dataframe(users_df, use_container_width=True)

            with st.form("create_user_form"):
                new_username = st.text_input("Nuevo usuario")
                new_full_name = st.text_input("Nombre completo")
                new_role = st.selectbox("Rol", ["Enfermería", "Médico", "Supervisor", "Administrador"])
                new_password = st.text_input("Contraseña", type="password")
                create_user_btn = st.form_submit_button("Crear usuario")
            if create_user_btn:
                try:
                    create_user(new_username, new_full_name, new_role, new_password)
                    st.success("Usuario creado correctamente")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ese usuario ya existe")

            if not users_df.empty:
                user_options = users_df.apply(lambda row: f"{row['id']} - {row['username']} - {row['full_name']}", axis=1).tolist()
                selected_user_label = st.selectbox("Selecciona usuario", user_options)
                selected_user_id = int(selected_user_label.split(" - ")[0])
                selected_row = users_df[users_df["id"] == selected_user_id].iloc[0]
                with st.form("edit_user_form"):
                    edit_full_name = st.text_input("Nombre completo", value=selected_row["full_name"])
                    roles = ["Enfermería", "Médico", "Supervisor", "Administrador"]
                    edit_role = st.selectbox("Rol", roles, index=roles.index(selected_row["role"]) if selected_row["role"] in roles else 0)
                    edit_active = st.selectbox("Estado", ["Activo", "Inactivo"], index=0 if int(selected_row["is_active"]) == 1 else 1)
                    update_user_btn = st.form_submit_button("Guardar cambios")
                if update_user_btn:
                    update_user(selected_user_id, edit_full_name, edit_role, 1 if edit_active == "Activo" else 0)
                    st.success("Usuario actualizado correctamente")
                    st.rerun()
