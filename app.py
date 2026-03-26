import io
import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

DB_FILE = "triage_hospital.db"

st.set_page_config(page_title="TRIAGE IA HOSPITAL - Revisada", page_icon="🏥", layout="wide")

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
    flujo_clinico: str
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, role, salt, password_hash, is_active FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    user = {"id": row[0], "username": row[1], "full_name": row[2], "role": row[3], "salt": row[4], "password_hash": row[5], "is_active": row[6]}
    if int(user["is_active"]) != 1:
        return None
    return user if hash_password(password, user["salt"]) == user["password_hash"] else None

def create_user(username: str, full_name: str, role: str, password: str):
    if not username.strip() or not full_name.strip() or not password.strip():
        raise ValueError("Todos los campos son obligatorios.")
    conn = get_conn()
    cur = conn.cursor()
    salt = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()[:32]
    password_hash = hash_password(password, salt)
    cur.execute("INSERT INTO users (username, full_name, role, salt, password_hash) VALUES (?, ?, ?, ?, ?)", (username.strip(), full_name.strip(), role, salt, password_hash))
    conn.commit()
    conn.close()

def update_user(user_id: int, full_name: str, role: str, is_active: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?", (full_name.strip(), role, int(is_active), int(user_id)))
    conn.commit()
    conn.close()

def load_users_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id DESC", conn)
    conn.close()
    return df

def get_shift_from_dt(dt_value) -> str:
    dt = pd.to_datetime(dt_value, errors="coerce")
    if pd.isna(dt):
        return "Desconocido"
    if 7 <= dt.hour < 14:
        return "Matutino"
    if 14 <= dt.hour < 21:
        return "Vespertino"
    return "Nocturno"

def calculate_wait_minutes(fecha_registro_value):
    dt = pd.to_datetime(fecha_registro_value, errors="coerce")
    if pd.isna(dt):
        return None
    return max(int((datetime.now() - dt.to_pydatetime()).total_seconds() // 60), 0)

def format_wait(wait_minutes):
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
    return f"<html><body><button onclick='window.print()'>Imprimir</button><h1>Hoja de Triage</h1><p><b>Folio:</b> {record.get('folio','')}</p><p><b>Nombre:</b> {record.get('nombre_paciente','')}</p><p><b>Flujo:</b> {record.get('flujo_clinico','')}</p><p><b>Semáforo:</b> {record.get('semaforo','')}</p><p><b>Acción:</b> {record.get('accion_sugerida','')}</p><p><b>Motivos:</b> {record.get('motivos','')}</p><p><b>Alertas:</b> {record.get('alertas','')}</p></body></html>"

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
    return {"folio": data.folio, "nombre_paciente": data.nombre_paciente, "semaforo": semaforo, "accion_sugerida": accion, "motivos": motivos, "alertas": alertas, "datos_capturados": asdict(data), "sepsis_score": data.sepsis_score, "sepsis_alerta": data.sepsis_alerta, "aviso_legal": "Herramienta de apoyo para priorización clínica. No sustituye el juicio clínico."}

def evaluar_discriminadores_universales(data: TriageInput):
    if data.estado_conciencia.strip().lower() == "inconsciente":
        return "NARANJA", ["Paciente inconsciente"], []
    if data.convulsiones:
        return "NARANJA", ["Convulsiones activas o recientes"], []
    if data.sangrado_activo:
        return "NARANJA", ["Sangrado activo"], []
    if data.saturacion_oxigeno < 90:
        return "NARANJA", [f"Saturación crítica: {data.saturacion_oxigeno}%"], ["Compromiso respiratorio"]
    if data.presion_sistolica < 90:
        return "NARANJA", [f"Hipotensión: TA sistólica {data.presion_sistolica} mmHg"], []
    return None, [], []

def evaluar_dolor_toracico(data: TriageInput):
    if data.dolor_toracico:
        if data.palidez_diaforesis or data.dificultad_respiratoria or data.saturacion_oxigeno < 94:
            return "NARANJA", ["Dolor torácico con alto riesgo cardiovascular"], ["Código Infarto"]
        return "AMARILLO", ["Dolor torácico"], []
    return None, [], []

def evaluar_respiratorio(data: TriageInput):
    if data.dificultad_respiratoria:
        if data.saturacion_oxigeno < 90 or data.frecuencia_respiratoria > 30:
            return "NARANJA", ["Compromiso respiratorio severo"], ["Compromiso respiratorio"]
        return "AMARILLO", ["Dificultad respiratoria"], ["Compromiso respiratorio"]
    return None, [], []

def evaluar_neurologico(data: TriageInput):
    if data.inicio_subito and (data.debilidad_unilateral or data.alteracion_habla or data.asimetria_facial):
        return "NARANJA", ["Déficit neurológico súbito"], ["Código Cerebro"]
    return None, [], []

def evaluar_sepsis(data: TriageInput):
    data.sepsis_score, data.sepsis_alerta = compute_sepsis_score(data)
    if data.sepsis_score >= 4:
        return "NARANJA", [f"Sepsis score alto: {data.sepsis_score}"], ["Código Sepsis"]
    if data.sepsis_score >= 2:
        return "AMARILLO", [f"Sepsis score intermedio: {data.sepsis_score}"], ["Código Sepsis"]
    return None, [f"Sepsis score: {data.sepsis_score}"], []

def evaluar_obstetrico(data: TriageInput):
    if not data.embarazo:
        return None, [], []
    if data.sangrado_vaginal:
        return "NARANJA", ["Sangrado vaginal en embarazo"], ["Código Mater"]
    if data.hipertension_embarazo and (data.cefalea_intensa or data.vision_borrosa):
        return "NARANJA", ["Datos de alarma obstétrica"], ["Código Mater"]
    if data.dolor_pelvico or data.movimientos_fetales_disminuidos:
        return "AMARILLO", ["Vigilancia obstétrica"], []
    return None, ["Paciente obstétrica"], []

def evaluar_trauma(data: TriageInput):
    if data.trauma_reciente:
        if data.sangrado_activo or data.presion_sistolica < 90:
            return "NARANJA", ["Trauma con datos de gravedad"], []
        return "AMARILLO", ["Trauma reciente estable"], []
    return None, [], []

def evaluar_dolor_abdominal(data: TriageInput):
    if "abdominal" in data.motivo_consulta.lower():
        if data.dolor_eva >= 8:
            return "AMARILLO", ["Dolor abdominal intenso"], []
        return "VERDE", ["Dolor abdominal sin datos de alarma mayores"], []
    return None, [], []

def ajustar_por_signos_vitales(prioridad: str, data: TriageInput):
    if data.saturacion_oxigeno < 90 or data.frecuencia_respiratoria > 30:
        return "NARANJA"
    if data.frecuencia_cardiaca > 130 and prioridad == "VERDE":
        return "AMARILLO"
    if data.dolor_eva >= 8 and prioridad == "VERDE":
        return "AMARILLO"
    if (data.glucosa_capilar < 70 or data.glucosa_capilar > 300) and prioridad == "VERDE":
        return "AMARILLO"
    return prioridad

def evaluar_triage(data: TriageInput):
    data.sepsis_score, data.sepsis_alerta = compute_sepsis_score(data)
    prioridad, motivos, alertas = evaluar_discriminadores_universales(data)
    if prioridad:
        return resultado(prioridad, "Valoración médica inmediata", motivos, alertas, data)
    mapping = {"Dolor torácico": evaluar_dolor_toracico, "Dificultad respiratoria": evaluar_respiratorio, "Neurológico": evaluar_neurologico, "Infección / Sepsis": evaluar_sepsis, "Obstétrico": evaluar_obstetrico, "Trauma": evaluar_trauma, "Dolor abdominal": evaluar_dolor_abdominal}
    if data.flujo_clinico in mapping:
        prioridad, motivos, alertas = mapping[data.flujo_clinico](data)
    else:
        prioridad, motivos, alertas = "VERDE", ["Paciente sin criterios de alta prioridad en flujo seleccionado"], []
    if prioridad is None:
        prioridad = "VERDE"
    prioridad = ajustar_por_signos_vitales(prioridad, data)
    accion = "Valoración médica inmediata" if prioridad == "NARANJA" else "Valoración médica prioritaria" if prioridad == "AMARILLO" else "Atención diferida"
    return resultado(prioridad, accion, motivos, alertas, data)

def save_triage(data: TriageInput, res: Dict[str, Any], tipo_registro: str = "Inicial"):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO triage_records (
            fecha_registro, tipo_registro, folio, nombre_paciente, edad, sexo, motivo_consulta,
            usuario_captura, rol_usuario, fecha_hora_ingreso, flujo_clinico,
            frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
            temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
            dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
            alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
            inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
            antecedente_hipertension, antecedente_diabetes, puede_caminar,
            embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo,
            cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos,
            sepsis_score, sepsis_alerta, semaforo, accion_sugerida, motivos, alertas, estado_operativo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tipo_registro, data.folio, data.nombre_paciente, data.edad, data.sexo, data.motivo_consulta,
        data.usuario_captura, data.rol_usuario, data.fecha_hora_ingreso, data.flujo_clinico,
        data.frecuencia_cardiaca, data.frecuencia_respiratoria, data.presion_sistolica, data.presion_diastolica,
        data.temperatura, data.saturacion_oxigeno, data.glucosa_capilar, data.dolor_eva, data.estado_conciencia,
        int(data.dolor_toracico), int(data.dificultad_respiratoria), int(data.fiebre), int(data.sangrado_activo), int(data.convulsiones),
        int(data.alteracion_mental), int(data.debilidad_unilateral), int(data.alteracion_habla), int(data.asimetria_facial),
        int(data.inicio_subito), int(data.sincope), int(data.palidez_diaforesis), int(data.trauma_reciente),
        int(data.antecedente_hipertension), int(data.antecedente_diabetes), int(data.puede_caminar),
        int(data.embarazo), data.semanas_gestacion, int(data.sangrado_vaginal), int(data.dolor_pelvico), int(data.hipertension_embarazo),
        int(data.cefalea_intensa), int(data.vision_borrosa), int(data.movimientos_fetales_disminuidos),
        data.sepsis_score, data.sepsis_alerta, res["semaforo"], res["accion_sugerida"], " | ".join(res["motivos"]), " | ".join(res["alertas"]) if res["alertas"] else "", "Pendiente"
    ))
    conn.commit(); conn.close()

def load_triage_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM triage_records ORDER BY id DESC", conn)
    conn.close()
    return df

def load_operational_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, fecha_registro, tipo_registro, folio, nombre_paciente, flujo_clinico, semaforo, accion_sugerida, usuario_captura, rol_usuario, estado_operativo, motivos, alertas FROM triage_records ORDER BY datetime(fecha_registro) DESC, id DESC", conn)
    conn.close()
    return df

def get_latest_patient_by_folio(folio: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        SELECT folio, nombre_paciente, edad, sexo, motivo_consulta, fecha_hora_ingreso, flujo_clinico,
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
    keys = ["folio","nombre_paciente","edad","sexo","motivo_consulta","fecha_hora_ingreso","flujo_clinico","frecuencia_cardiaca","frecuencia_respiratoria","presion_sistolica","presion_diastolica","temperatura","saturacion_oxigeno","glucosa_capilar","dolor_eva","estado_conciencia","dolor_toracico","dificultad_respiratoria","fiebre","sangrado_activo","convulsiones","alteracion_mental","debilidad_unilateral","alteracion_habla","asimetria_facial","inicio_subito","sincope","palidez_diaforesis","trauma_reciente","antecedente_hipertension","antecedente_diabetes","puede_caminar","embarazo","semanas_gestacion","sangrado_vaginal","dolor_pelvico","hipertension_embarazo","cefalea_intensa","vision_borrosa","movimientos_fetales_disminuidos"]
    patient = dict(zip(keys, row))
    for f in ["dolor_toracico","dificultad_respiratoria","fiebre","sangrado_activo","convulsiones","alteracion_mental","debilidad_unilateral","alteracion_habla","asimetria_facial","inicio_subito","sincope","palidez_diaforesis","trauma_reciente","antecedente_hipertension","antecedente_diabetes","puede_caminar","embarazo","sangrado_vaginal","dolor_pelvico","hipertension_embarazo","cefalea_intensa","vision_borrosa","movimientos_fetales_disminuidos"]:
        patient[f] = bool(patient[f])
    return patient

def update_operational_status(record_id: int, estado_operativo: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE triage_records SET estado_operativo = ? WHERE id = ?", (estado_operativo, int(record_id)))
    conn.commit(); conn.close()

def render_obstetric_fields(prefix: str, defaults=None):
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

def show_result_block(res: Dict[str, Any]):
    st.subheader("Resultado del triage")
    if res["semaforo"] == "NARANJA":
        st.markdown(f"""<div class="orange-box"><h2>🟠 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)
    elif res["semaforo"] == "AMARILLO":
        st.markdown(f"""<div class="yellow-box"><h2>🟡 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="green-box"><h2>🟢 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Motivos de clasificación**")
        for motivo in res["motivos"]:
            st.write(f"- {motivo}")
    with c2:
        st.markdown("**Sepsis score**")
        st.write(f"Puntaje: {res['sepsis_score']}")
        st.write(f"Interpretación: {res['sepsis_alerta']}")
    st.markdown("**Alertas activadas**")
    if res["alertas"]:
        for alerta in res["alertas"]:
            st.write(f"- {alerta}")
    else:
        st.write("- Sin alertas específicas")
    st.caption(res["aviso_legal"])

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    st.title("🔐 Login - TRIAGE IA HOSPITAL")
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
        flujos = ["General", "Dolor torácico", "Dificultad respiratoria", "Neurológico", "Infección / Sepsis", "Obstétrico", "Trauma", "Dolor abdominal"]
        flujo_clinico = st.selectbox("Motivo principal / flujo clínico", flujos)
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
                estado_conciencia = st.selectbox("Estado de conciencia", ["alerta", "somnoliento", "confuso", "inconsciente"])

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

            if flujo_clinico == "Obstétrico":
                embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo, cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos = render_obstetric_fields("ini")
            else:
                embarazo, semanas_gestacion, sangrado_vaginal, dolor_pelvico, hipertension_embarazo, cefalea_intensa, vision_borrosa, movimientos_fetales_disminuidos = (False, 0, False, False, False, False, False, False)

            submitted = st.form_submit_button("Clasificar paciente")

        if submitted:
            data = TriageInput(folio, nombre_paciente, int(edad), sexo, motivo_consulta, user["full_name"], user["role"], fecha_hora_ingreso, flujo_clinico, int(frecuencia_cardiaca), int(frecuencia_respiratoria), int(presion_sistolica), int(presion_diastolica), float(temperatura), int(saturacion_oxigeno), int(glucosa_capilar), int(dolor_eva), estado_conciencia, bool(dolor_toracico), bool(dificultad_respiratoria), bool(fiebre), bool(sangrado_activo), bool(convulsiones), bool(alteracion_mental), bool(debilidad_unilateral), bool(alteracion_habla), bool(asimetria_facial), bool(inicio_subito), bool(sincope), bool(palidez_diaforesis), bool(trauma_reciente), bool(antecedente_hipertension), bool(antecedente_diabetes), bool(puede_caminar), bool(embarazo), int(semanas_gestacion), bool(sangrado_vaginal), bool(dolor_pelvico), bool(hipertension_embarazo), bool(cefalea_intensa), bool(vision_borrosa), bool(movimientos_fetales_disminuidos))
            res = evaluar_triage(data)
            save_triage(data, res, "Inicial")
            show_result_block(res)
            st.success("Paciente guardado en la base de datos")

    with tab2:
        st.title("🔁 REVALORACIÓN DEL PACIENTE")
        st.info("Usa el folio para cargar la última valoración del paciente y registrar una nueva revaloración.")
        df = load_triage_df()
        if df.empty:
            st.warning("No hay registros previos para revalorar.")
        else:
            st.dataframe(df[["folio","nombre_paciente","flujo_clinico","fecha_registro","semaforo"]].head(20), use_container_width=True)

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
            st.dataframe(oper_df, use_container_width=True)

    with tab4:
        st.title("📊 DASHBOARD")
        df = load_triage_df()
        if df.empty:
            st.warning("No hay registros en la base de datos.")
        else:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df["minutos_espera"] = df["fecha_registro"].apply(calculate_wait_minutes)
            df["turno"] = df["fecha_registro"].apply(get_shift_from_dt)
            st.dataframe(df, use_container_width=True)
            st.download_button("Descargar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="triage_revisada.csv", mime="text/csv")
            st.download_button("Descargar Excel", data=dataframe_to_excel_bytes(df), file_name="triage_revisada.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab5:
        if user["role"] != "Administrador":
            st.warning("Solo el Administrador puede gestionar usuarios.")
        else:
            st.title("👥 GESTIÓN DE USUARIOS")
            users_df = load_users_df()
            st.dataframe(users_df, use_container_width=True)
