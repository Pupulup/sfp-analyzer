import streamlit as st
import pandas as pd
import numpy as np
import re
import csv

st.set_page_config(page_title="Huawei Link Analyzer", layout="wide")

DL_WARN, DL_CRIT = 3.5, 4
UL_WARN, UL_CRIT = 3.5, 4

def microwatt_to_dbm(val):
    try:
        s = str(val).replace('"', '').replace('=', '').strip()
        if s.lower() in ['invalid', 'null', 'nan', '', '0']:
            return -99.0
        num = pd.to_numeric(s, errors='coerce')
        if pd.isna(num) or num <= 0:
            return -99.0
        mw = (num * 0.1) / 1000
        return round(10 * np.log10(mw), 2)
    except:
        return -99.0

def normalize_header(headers):
    mapping = {
        'Chain No.': 'Chain',
        'Head Slot No.': 'BBU Slot',
        'Head Port No.': 'BBU Port',
        'TX optical power(0.1microwatt)': 'TX_Raw',
        'RX optical power(0.1microwatt)': 'RX_Raw',
        'Cabinet No.': 'Cabinet',
        'Subrack No.': 'Subrack',
        'Slot No.': 'Slot',
        'Port No.': 'Port'
    }
    return [mapping.get(h, h) for h in headers]

def format_power(val):
    return f"{val} dBm" if val != -99.0 else "No Data"

def get_status_color(val, warn, crit):
    if val == -99.0: return "#6c757d"
    return "#FF4B4B" if val > crit else "#FFA500" if val > warn else "#00C853"

st.title("Херня, не спользуйте")

uploaded_file = st.file_uploader("Загрузите CSV", type="csv")
if not uploaded_file:
    st.stop()

content = uploaded_file.getvalue().decode("utf-8", errors="replace")
lines = content.splitlines()

sfp_rows, chain_rows = [], []
headers, mode = None, None
current_site = "UNKNOWN"

for line in lines:
    raw = line.strip()
    clean = raw.replace('"', '').replace('\t', '')
    if "78_" in clean:
        m = re.search(r'(78_[A-Za-z0-9_]+)', clean)
        if m: current_site = m.group(1)
    if "Cabinet No." in clean and "TX optical power" in clean:
        mode, headers = "SFP", normalize_header(next(csv.reader([raw])))
        continue
    if "Chain No." in clean:
        mode, headers = "CHAIN", normalize_header(next(csv.reader([raw])))
        continue
    if not headers or any(x in clean for x in ["RETCODE", "---", "END"]):
        headers, mode = None, None
        continue
    try:
        row = next(csv.reader([raw]))
        if not row or not row[0].replace('"', '').strip().isdigit(): continue
        item = {headers[i]: row[i].strip().replace('"', '') for i in range(min(len(headers), len(row)))}
        item["Site"] = current_site
        if mode == "SFP":
            item["TX_dBm"] = microwatt_to_dbm(item.get("TX_Raw"))
            item["RX_dBm"] = microwatt_to_dbm(item.get("RX_Raw"))
            sfp_rows.append(item)
        elif mode == "CHAIN":
            chain_rows.append(item)
    except: continue

df_sfp = pd.DataFrame(sfp_rows)
df_chain = pd.DataFrame(chain_rows)

if df_sfp.empty:
    st.error("Нет данных DSP SFP")
    st.stop()

site = st.selectbox("БС", sorted(df_sfp["Site"].unique()))
s_sfp = df_sfp[df_sfp["Site"] == site]
s_chains = df_chain[df_chain["Site"] == site]

st.header("Сопоставление портов")

results = []
for _, chain in s_chains.iterrows():
    ch_id = chain["Chain"]
    slot = chain["BBU Slot"]
    port_bbu = chain["BBU Port"]

    b_match = s_sfp[(s_sfp["Slot"] == slot) & (s_sfp["Port"] == port_bbu)]

    next_port = str(int(port_bbu) + 1)
    r_match = s_sfp[(s_sfp["Slot"] == slot) & (s_sfp["Port"] == next_port)]

    if r_match.empty:
        r_match = s_sfp[s_sfp["Subrack"] == ch_id]

    if b_match.empty: continue

    b = b_match.iloc[0]
    r = r_match.iloc[0] if not r_match.empty else None

    dl_loss = round(b["TX_dBm"] - r["RX_dBm"], 2) if (r is not None and b["TX_dBm"] != -99 and r["RX_dBm"] != -99) else -99
    ul_loss = round(r["TX_dBm"] - b["RX_dBm"], 2) if (r is not None and r["TX_dBm"] != -99 and b["RX_dBm"] != -99) else -99

    with st.container():
        st.subheader(f"⛓️ Chain {ch_id}")
        c1, c2, c3 = st.columns([1, 2, 1])

        with c1:
            st.info(f"**BBU (Port {b['Port']})**")
            st.write(f"TX: {format_power(b['TX_dBm'])}")
            st.write(f"RX: {format_power(b['RX_dBm'])}")

        with c2:
            if r is not None and dl_loss != -99:
                st.markdown(f"<div style='text-align:center; color:{get_status_color(dl_loss, DL_WARN, DL_CRIT)}'><b>DL: {dl_loss} dB</b></div>", unsafe_allow_html=True)
                st.progress(min(max(dl_loss/10, 0.0), 1.0))
                st.markdown(f"<div style='text-align:center; color:{get_status_color(ul_loss, UL_WARN, UL_CRIT)}; margin-top:10px;'><b>UL: {ul_loss} dB</b></div>", unsafe_allow_html=True)
                st.progress(min(max(ul_loss/10, 0.0), 1.0))
            else:
                st.warning("Пара (RRU) не определена или нет данных в Port " + next_port)

        with c3:
            if r is not None:
                st.success(f"**RRU (Port {r['Port']})**")
                st.write(f"RX: {format_power(r['RX_dBm'])}")
                st.write(f"TX: {format_power(r['TX_dBm'])}")
            else:
                st.error("**RRU Not Found**")
        st.divider()



