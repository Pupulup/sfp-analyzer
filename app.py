import streamlit as st
import pandas as pd
import numpy as np
import io
import re

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

uploaded_file = st.file_uploader("В MML-командах пропишите DSP SFP и LST RRUCHAIN, экспортируйте в csv файл и загрузите)", type="csv")

if uploaded_file:
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        lines = content.splitlines()
        
        all_data = []
        current_site = "Unknown Site"
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if "78_" in line:
                site_match = re.search(r'78_\d+[A-Z0-9_]*', line)
                if site_match:
                    current_site = site_match.group()

            if "Cabinet No." in line and "TX optical power" in line:
                headers = [c.strip().replace('"', '') for c in line.split(',')]
                table_rows = []
      
                j = i + 1
                while j < len(lines):
                    data_line = lines[j].strip()
                    if not data_line or "END" in data_line or "---" in data_line:
                        break
                    parts = next(io.csv.reader([data_line]))
                    if len(parts) >= len(headers) - 2:
                        row_dict = dict(zip(headers, [p.strip() for p in parts]))
                        row_dict['Site Name'] = current_site
                        table_rows.append(row_dict)
                    j += 1
                
                if table_rows:
                    all_data.extend(table_rows)
                i = j 
            
            i += 1

        if all_data:
            df = pd.DataFrame(all_data)
            cols = {
                'subrack': 'Subrack No.',
                'slot': 'Slot No.',
                'port': 'Port No.',
                'tx': 'TX optical power(0.1microwatt)',
                'rx': 'RX optical power(0.1microwatt)'
            }

            df['TX_dBm'] = df[cols['tx']].apply(microwatt_to_dbm)
            df['RX_dBm'] = df[cols['rx']].apply(microwatt_to_dbm)
            active_sfp = df[df['TX_dBm'] > -90].copy()
            active_sfp['Attenuation'] = round(active_sfp['TX_dBm'] - active_sfp['RX_dBm'], 2)

            st.header("📊 Сводные данные по всем объектам")
            
            c1, c2 = st.columns(2)
            with c1:
                selected_sites = st.multiselect("Выберите БС", sorted(active_sfp['Site Name'].unique()), default=sorted(active_sfp['Site Name'].unique()))
            with c2:
                selected_subs = st.multiselect("Выберите Subrack", sorted(active_sfp[cols['subrack']].unique()), default=sorted(active_sfp[cols['subrack']].unique()))

            filtered_df = active_sfp[
                (active_sfp['Site Name'].isin(selected_sites)) & 
                (active_sfp[cols['subrack']].isin(selected_subs))
            ]

            m1, m2, m3 = st.columns(3)
            m1.metric("Активных портов", len(filtered_df))
            m2.metric("Средний RX", f"{filtered_df['RX_dBm'].mean():.2f} dBm" if not filtered_df.empty else "0")
            m3.metric("Критические (<-8dBm)", len(filtered_df[filtered_df['RX_dBm'] < -8]))

            def color_attenuation(val):
                if val > 8: return 'background-color: #ff4b4b; color: white' 
                if val > 5: return 'background-color: #ffa500'
                return ''

            display_cols = ['Site Name', cols['subrack'], cols['slot'], cols['port'], 'TX_dBm', 'RX_dBm', 'Attenuation']
            st.dataframe(
                filtered_df[display_cols].style.applymap(color_attenuation, subset=['Attenuation']),
                use_container_width=True
            )

            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("Скачать результат CSV", csv, "sfp_report.csv", "text/csv")

        else:
            st.warning("В файле не обнаружено данных DSP SFP. Убедитесь, что вы загружаете правильный отчет.")

    except Exception as e:
        st.error(f"Ошибка: {e}")
