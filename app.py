import streamlit as st
import numpy as np
import re
import csv

def calculate_dbm(val_str):
    try:
        s = val_str.replace('"', '').replace('=', '').strip()
        val = float(s)
        if val <= 0: return -99.0
        mw = (val * 0.1) / 1000
        return round(10 * np.log10(mw), 2)
    except:
        return -99.0

st.set_page_config(page_title="SFP Analyzer", layout="wide")
st.title("В MML командах DSP SFP + LST RRUCHAIN -> экспорт в CSV")

uploaded_file = st.file_uploader("Загрузите CSV файл", type="csv")

if uploaded_file:
    content = uploaded_file.getvalue().decode("utf-8", errors="replace")
    lines = content.splitlines()

    data_structure = {}
    current_bts = "Unknown"
    current_cmd = None

    for line in lines:
        if not line.strip(): continue
        row = [x.strip().replace('"', '') for x in next(csv.reader([line]))]
        if "78_" in line:
            match = re.search(r'(78_[A-Za-z0-9_]+)', line)
            if match:
                current_bts = match.group(1)
                if current_bts not in data_structure:
                    data_structure[current_bts] = {}
        if "LST RRUCHAIN" in line: current_cmd = "LST RRUCHAIN"
        elif "DSP SFP" in line: current_cmd = "DSP SFP"

        if current_cmd and len(row) > 4:
            if current_bts not in data_structure: data_structure[current_bts] = {}
            if current_cmd not in data_structure[current_bts]:
                data_structure[current_bts][current_cmd] = {"headers": [], "values": []}

            if row[0].isdigit():
                data_structure[current_bts][current_cmd]["values"].append(row)
            else:
                if not data_structure[current_bts][current_cmd]["headers"]:
                    if "Chain No." in row or "Cabinet No." in row:
                        data_structure[current_bts][current_cmd]["headers"] = row

    for bts, cmds in data_structure.items():
        st.header(f"БС: {bts}")

        if "LST RRUCHAIN" not in cmds or "DSP SFP" not in cmds:
            st.error("В файле не найдены секции LST RRUCHAIN или DSP SFP")
            continue

        chains_data = cmds["LST RRUCHAIN"]
        sfps_data = cmds["DSP SFP"]

        h_ch = chains_data["headers"]
        idx_c_no = h_ch.index("Chain No.")
        idx_h_sub = h_ch.index("Head Subrack No.")
        idx_h_slot = h_ch.index("Head Slot No.")
        idx_h_port = h_ch.index("Head Port No.")

        h_sfp = sfps_data["headers"]
        idx_sfp_sub = h_sfp.index("Subrack No.")
        idx_sfp_slot = h_sfp.index("Slot No.")
        idx_sfp_port = h_sfp.index("Port No.")
        idx_sfp_tx = h_sfp.index("TX optical power(0.1microwatt)")
        idx_sfp_rx = h_sfp.index("RX optical power(0.1microwatt)")

        found_count = 0

        for ch_row in chains_data["values"]:
            c_no = ch_row[idx_c_no]
            h_sub = ch_row[idx_h_sub]
            h_slot = ch_row[idx_h_slot]
            h_port = ch_row[idx_h_port]

            bbu_row = rru_row = None
            for s_row in sfps_data["values"]:
                if (s_row[idx_sfp_sub] == h_sub and s_row[idx_sfp_slot] == h_slot and s_row[idx_sfp_port] == h_port):
                    bbu_row = s_row
                if s_row[idx_sfp_sub] == c_no:
                    rru_row = s_row

            if bbu_row and rru_row:
                found_count += 1
                b_tx = calculate_dbm(bbu_row[idx_sfp_tx])
                b_rx = calculate_dbm(bbu_row[idx_sfp_rx])
                r_tx = calculate_dbm(rru_row[idx_sfp_tx])
                r_rx = calculate_dbm(rru_row[idx_sfp_rx])

                dl_loss = round(b_tx - r_rx, 2)
                ul_loss = round(r_tx - b_rx, 2)

                def color_loss(loss):
                    if loss > 4: return "#ff4b4b"  # красный
                    elif loss >= 3.5: return "#ffa500"  # оранжевый
                    else: return "#fffffff"  # черный

                with st.expander(f" {c_no} | BBU Slot {h_slot} Port {h_port}", expanded=True):
                    c1, c2, c3 = st.columns([1, 1, 1])
                    c1.markdown(
                        f"<div style='font-size:14px; text-align:center;'>"
                        f"<b>BBU TX:</b> {b_tx} dBm<br>"
                        f"<b>BBU RX:</b> {b_rx} dBm"
                        f"</div>", unsafe_allow_html=True
                    )
                    c2.markdown(
                        f"<div style='font-size:14px; text-align:center;'>"
                        f"<b style='color:{color_loss(dl_loss)}'>Loss DL: {dl_loss} dB</b><br>"
                        f"<b style='color:{color_loss(ul_loss)}'>Loss UL: {ul_loss} dB</b>"
                        f"</div>", unsafe_allow_html=True
                    )
                    c3.markdown(
                        f"<div style='font-size:14px; text-align:center;'>"
                        f"<b>RRU RX:</b> {r_rx} dBm<br>"
                        f"<b>RRU TX:</b> {r_tx} dBm"
                        f"</div>", unsafe_allow_html=True
                    )

            else:
                st.info(f"Chain {c_no}: Данные RRU (Subrack {c_no}) не найдены в DSP SFP")

        if found_count == 0:
            st.warning("Совпадений не найдено. Убедитесь, что в DSP SFP есть данные для удаленных Subrack.")



