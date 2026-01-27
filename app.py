import streamlit as st
import pandas as pd
import numpy as np
import io
import re
import csv

def microwatt_to_dbm(val):
    try:
        if isinstance(val, str):
            val = val.replace('"', '').strip()
        num = pd.to_numeric(val, errors='coerce')
        if pd.isna(num) or num <= 0:
            return -99.0
        mw = (num * 0.1) / 1000
        return round(10 * np.log10(mw), 2)
    except:
        return -99.0

st.set_page_config(page_title="Multi-BS SFP Analyzer", layout="wide")
st.title("Анализ оптики")

uploaded_file = st.file_uploader("Загрузите CSV отчет", type="csv")

if uploaded_file:
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        lines = content.splitlines()
        
        all_data = []
        current_site = "Unknown Site"
        
        i = 0
        while i < len(lines):
            line_raw = lines[i]
            line_clean = line_raw.replace('"', '').strip()
            
            if "78_" in line_clean:
                site_match = re.search(r'78_\d+[A-Z0-9_]*', line_clean)
                if site_match:
                    current_site = site_match.group()

            if "Cabinet No." in line_clean and "TX optical power" in line_clean:
                reader = csv.reader([line_raw])
                headers = [c.strip().replace('"', '') for c in next(reader)]
                
                j = i + 1
                while j < len(lines):
                    data_line = lines[j].strip()
                    if not data_line or "---" in data_line or "RETCODE" in data_line:
                        break
                    
                    data_reader = csv.reader([lines[j]])
                    parts = next(data_reader)
                    
                    if len(parts) >= len(headers) - 3:
                        row_dict = dict(zip(headers, [p.strip() for p in parts]))
                        row_dict['Site Name'] = current_site
                        all_data.append(row_dict)
                    j += 1
                i = j
            i += 1

        if all_data:
            df = pd.DataFrame(all_data)
            df.columns = [c.strip() for c in df.columns]

            col_tx = next((c for c in df.columns if "TX optical power" in c), None)
            col_rx = next((c for c in df.columns if "RX optical power" in c), None)
            col_sub = next((c for c in df.columns if "Subrack No." in c), "Subrack No.")
            col_slot = next((c for c in df.columns if "Slot No." in c), "Slot No.")
            col_port = next((c for c in df.columns if "Port No." in c), "Port No.")

            if col_tx and col_rx:
                df['TX_dBm'] = df[col_tx].apply(microwatt_to_dbm)
                df['RX_dBm'] = df[col_rx].apply(microwatt_to_dbm)
                
                active_sfp = df[df['TX_dBm'] > -90].copy()
                active_sfp['Attenuation'] = round(active_sfp['TX_dBm'] - active_sfp['RX_dBm'], 2)

                st.header("Сводные данные")
                
                c1, c2 = st.columns(2)
                with c1:
                    sites = sorted(active_sfp['Site Name'].unique())
                    sel_sites = st.multiselect("Выберите БС", sites, default=sites)
                with c2:
                    subs = sorted(active_sfp[col_sub].unique())
                    sel_subs = st.multiselect("Выберите Subrack", subs, default=subs)

                filtered_df = active_sfp[
                    (active_sfp['Site Name'].isin(sel_sites)) & 
                    (active_sfp[col_sub].isin(sel_subs))
                ]

                m1, m2, m3 = st.columns(3)
                m1.metric("Активных SFP", len(filtered_df))
                m2.metric("Ср. RX", f"{filtered_df['RX_dBm'].mean():.2f} dBm" if not filtered_df.empty else "0")
                m3.metric("Критические (<-8dBm)", len(filtered_df[filtered_df['RX_dBm'] < -8]))

                def color_attenuation(val):
                    if val > 8: return 'background-color: #ff4b4b; color: white' 
                    if val > 5: return 'background-color: #ffa500'
                    return ''

                display_cols = ['Site Name', col_sub, col_slot, col_port, 'TX_dBm', 'RX_dBm', 'Attenuation']
                st.dataframe(
                    filtered_df[display_cols].style.applymap(color_attenuation, subset=['Attenuation']),
                    use_container_width=True
                )
                
                csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button("Скачать результат", csv_data, "sfp_report.csv", "text/csv")
            else:
                st.error("Колонки TX/RX не найдены")
        else:
            st.warning("Данные не найдены")

    except Exception as e:
        st.error(f"Ошибка: {e}")
