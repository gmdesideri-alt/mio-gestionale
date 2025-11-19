import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestionale Web", layout="wide", page_icon="📈")

# --- CONFIGURAZIONE SICUREZZA ---
PASSWORD_SEGRET = "1989"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- GESTIONE CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource
def get_gspread_client():
    # Carica le credenziali dai Secrets di Streamlit
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client

def load_all_data():
    """Carica tutti i dati da Google Sheets trasformandoli in liste di dizionari"""
    try:
        client = get_gspread_client()
        sh = client.open_by_url(st.secrets["sheets"]["url"])
        
        # Leggiamo i 4 fogli. Se sono vuoti restituisce lista vuota
        dati = {}
        keys = ["Commesse", "Attivita", "Finanza", "Note"]
        
        for k in keys:
            try:
                ws = sh.worksheet(k)
                records = ws.get_all_records() # Ritorna lista di dict
                # Convertiamo tutto in stringa per evitare errori di tipi misti
                for r in records:
                    for field in r:
                        r[field] = str(r[field])
                dati[k.lower()] = records
            except gspread.WorksheetNotFound:
                sh.add_worksheet(k, 100, 10)
                dati[k.lower()] = []
            except Exception:
                dati[k.lower()] = []
                
        return dati
    except Exception as e:
        st.error(f"Errore connessione Database: {e}")
        return {"commesse": [], "attivita": [], "finanza": [], "note": []}

def sync_sheet(key_dati, sheet_name):
    """
    Sovrascrive un intero foglio (tab) con i dati attuali della sessione.
    """
    try:
        client = get_gspread_client()
        sh = client.open_by_url(st.secrets["sheets"]["url"])
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(sheet_name, 100, 10)
        
        data = st.session_state['dati'][key_dati]
        
        ws.clear() # Pulisce tutto
        if data:
            # Prende le chiavi dal primo elemento per fare l'header
            headers = list(data[0].keys())
            # Prepara i dati come matrice
            rows = [headers]
            for d in data:
                rows.append([d.get(h, "") for h in headers])
            ws.update(rows)
        else:
            pass # Lascia vuoto
    except Exception as e:
        st.error(f"Errore salvataggio {sheet_name}: {e}")

def timestamp_now():
    return datetime.now().strftime("%d/%m/%Y %H:%M")

# --- INIZIALIZZAZIONE DATI ---
if 'dati' not in st.session_state:
    # Inizializza struttura vuota temporanea finché non carica
    st.session_state['dati'] = {"commesse": [], "attivita": [], "finanza": [], "note": []}
    try:
        st.session_state['dati'] = load_all_data()
    except:
        pass

# --- FUNZIONI LOGICHE ---
def calc_saldo(cid):
    dov, inc = 0.0, 0.0
    for f in st.session_state['dati']["finanza"]:
        if str(f.get("commessa")) == str(cid):
            try: v = float(str(f["importo"]).replace(",", "."))
            except: v = 0.0
            if f["tipo"] == "Incasso": inc += v
            elif f["tipo"] in ["Preventivo", "Spesa Anticipata"]: dov += v
    return round(dov - inc, 2)

def registra_evento_auto(cid, testo):
    st.session_state['dati']["note"].append({
        "commessa": str(cid), "testo": f"[AUTO] {testo}", "data": timestamp_now()
    })
    sync_sheet("note", "Note") # Salva subito le note

def genera_pdf_lista():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16); c.drawString(50, h-50, "ELENCO COMMESSE")
    c.setFont("Helvetica", 10); c.drawString(50, h-70, f"Generato il: {timestamp_now()}")
    c.line(50, h-80, w-50, h-80); y = h-100
    
    for comm in st.session_state['dati']["commesse"]:
        saldo = calc_saldo(comm['id'])
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"[{comm['id']}] {comm['cliente']}")
        c.setFont("Helvetica", 10)
        c.drawString(400, y, f"Saldo: {saldo}€")
        y -= 20
        if y < 50: c.showPage(); y = h-50
    
    c.save()
    buffer.seek(0)
    return buffer

# --- GESTIONE LOGIN ---
if 'loggato' not in st.session_state: st.session_state['loggato'] = False

if not st.session_state['loggato']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Accesso Cloud")
        pwd = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi", type="primary"):
            if pwd == PASSWORD_SEGRET:
                st.session_state['loggato'] = True
                st.rerun()
            else:
                st.error("Password Errata")
    st.stop()

# --- MENU LATERALE ---
st.sidebar.title("MENU")
if st.sidebar.button("🔄 Ricarica Dati"):
    st.session_state['dati'] = load_all_data()
    st.success("Dati aggiornati dal cloud!")

page = st.sidebar.radio("Navigazione:", ["Dashboard", "Attività Globali", "Finanza Globale"])

# --- PAGE: DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Dashboard Commesse")
    
    col_s, col_b = st.columns([3, 1])
    search = col_s.text_input("🔍 Cerca Cliente/Commessa...", "")
    
    with col_b:
        with st.popover("➕ Nuova Commessa"):
            with st.form("new_comm"):
                new_id = st.text_input("ID (es. 100)")
                new_cl = st.text_input("Cliente")
                new_tel = st.text_input("Telefono")
                new_em = st.text_input("Email")
                if st.form_submit_button("Salva"):
                    if new_id and new_cl:
                        # Aggiungi in sessione
                        st.session_state['dati']["commesse"].append({
                            "id": new_id, "cliente": new_cl, "telefono": new_tel, 
                            "email": new_em, "data": timestamp_now().split(" ")[0]
                        })
                        # Salva su Google Sheets
                        sync_sheet("commesse", "Commesse")
                        registra_evento_auto(new_id, f"Creata commessa: {new_cl}")
                        st.success("Creata!")
                        st.rerun()
    
    st.divider()
    
    # Lista
    lista = st.session_state['dati']["commesse"]
    filtrati = [c for c in lista if search.lower() in str(c['cliente']).lower() or search in str(c['id'])]
    
    for c in filtrati:
        saldo = calc_saldo(c['id'])
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.subheader(f"{c['cliente']}")
            st.caption(f"ID: {c['id']} | Tel: {c.get('telefono','-')}")
        with col2:
            col_text = "green" if saldo <= 0 else "red"
            st.markdown(f"#### Saldo: :{col_text}[{saldo} €]")
        with col3:
            if st.button("📂 Apri", key=f"btn_{c['id']}"):
                st.session_state['sel_commessa'] = c
                st.rerun()
        st.divider()

    # --- MODALE DETTAGLIO ---
    if 'sel_commessa' in st.session_state:
        sel = st.session_state['sel_commessa']
        st.markdown("---")
        col_h1, col_h2 = st.columns([4,1])
        col_h1.header(f"Dettaglio: {sel['cliente']}")
        if col_h2.button("❌ Chiudi", type="secondary"):
            del st.session_state['sel_commessa']
            st.rerun()
            
        tab_task, tab_fin, tab_note = st.tabs(["Attività", "Finanza", "Note"])
        
        with tab_task:
            with st.form("add_t"):
                c1, c2 = st.columns([3,1])
                desc = c1.text_input("Descrizione task")
                dt = c2.date_input("Scadenza")
                if st.form_submit_button("Aggiungi Task"):
                    st.session_state['dati']["attivita"].append({
                        "commessa": str(sel['id']), "descrizione": desc, 
                        "stato": "Da fare", "data": dt.strftime("%d/%m/%Y")
                    })
                    sync_sheet("attivita", "Attivita")
                    registra_evento_auto(sel['id'], f"Task aggiunto: {desc}")
                    st.rerun()
            
            tasks = [t for t in st.session_state['dati']["attivita"] if str(t.get("commessa")) == str(sel['id'])]
            for t in tasks:
                done = t.get("stato") == "Fatto"
                c_chk, c_txt, c_del = st.columns([0.5, 4, 0.5])
                if c_chk.checkbox("", value=done, key=f"chk_{t['descrizione']}_{sel['id']}"):
                     if not done:
                         t["stato"] = "Fatto"
                         sync_sheet("attivita", "Attivita")
                         st.rerun()
                elif done:
                     t["stato"] = "Da fare"
                     sync_sheet("attivita", "Attivita")
                     st.rerun()
                     
                st_txt = f"~~{t['descrizione']}~~" if done else t['descrizione']
                c_txt.markdown(st_txt)
                
                if c_del.button("🗑", key=f"del_t_{t['descrizione']}_{sel['id']}"):
                    st.session_state['dati']["attivita"].remove(t)
                    sync_sheet("attivita", "Attivita")
                    st.rerun()
                    
        with tab_fin:
            with st.expander("➕ Registra Movimento"):
                with st.form("add_f"):
                    ftype = st.selectbox("Tipo", ["Preventivo", "Spesa Anticipata", "Incasso"])
                    fimp = st.number_input("Importo", min_value=0.0, step=50.0)
                    fdesc = st.text_input("Descrizione")
                    if st.form_submit_button("Salva"):
                        st.session_state['dati']["finanza"].append({
                            "commessa": str(sel['id']), "tipo": ftype, 
                            "importo": str(fimp), "desc": fdesc, 
                            "data": timestamp_now().split(" ")[0]
                        })
                        sync_sheet("finanza", "Finanza")
                        st.rerun()
            
            fins = [f for f in st.session_state['dati']["finanza"] if str(f.get("commessa")) == str(sel['id'])]
            if fins:
                st.dataframe(pd.DataFrame(fins)[["data", "tipo", "importo", "desc"]], use_container_width=True)
            
        with tab_note:
            ntxt = st.text_area("Nuova Nota")
            if st.button("Salva Nota"):
                if ntxt:
                    registra_evento_auto(sel['id'], ntxt)
                    st.success("Nota salvata")
                    st.rerun()
            
            notes = [n for n in st.session_state['dati']["note"] if str(n.get("commessa")) == str(sel['id'])]
            for n in reversed(notes):
                st.info(f"{n['data']}\n\n{n['testo']}")

# --- PAGE: ATTIVITÀ GLOBALI ---
elif page == "Attività Globali":
    st.title("To-Do List Aziendale")
    tasks = st.session_state['dati']["attivita"]
    df = pd.DataFrame(tasks)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nessuna attività registrata")

# --- PAGE: FINANZA GLOBALE ---
elif page == "Finanza Globale":
    st.title("Economia Generale")
    tot_crediti = 0
    for c in st.session_state['dati']["commesse"]:
        s = calc_saldo(c['id'])
        if s > 0: tot_crediti += s
    
    st.metric("Totale da Incassare", f"{tot_crediti} €")
    
    st.subheader("Dettaglio Movimenti")
    df_fin = pd.DataFrame(st.session_state['dati']["finanza"])
    if not df_fin.empty:
        st.dataframe(df_fin, use_container_width=True)