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

st.set_page_config(page_title="SFP Sector Analyzer", layout="wide")
st.title("Анализ затуханий")

uploaded_file = st.file_uploader("В MML-командах вводим команды DSP SFP и LST RRUCHAIN, экспортируем в CSV, сюда грузим получившийся CSV отчет", type="csv")

if uploaded_file:
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        lines = content.splitlines()
        
        all_data = []
        current_site = "Unknown"
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if "78_" in line:
                site_match = re.search(r'BTS_78_\d+_[A-Z0-9_]+', line)
                if site_match:
                    current_site = site_match.group().replace('"', '')

            if "Cabinet No." in line and "TX optical power" in line:
                header_line = i
                table_lines = [lines[header_line]]
                j = header_line + 1
                while j < len(lines) and "Cabinet No." not in lines[j] and lines[j].strip() != "" and "---" not in lines[j]:
                    if lines[j].startswith('"'):
                        table_lines.append(lines[j])
                    j += 1
                
                data_io = io.StringIO("\n".join(table_lines))
                temp_df = pd.read_csv(data_io, quotechar='"', skipinitialspace=True)
                temp_df.columns = [c.strip().replace('"', '') for c in temp_df.columns]

                temp_df['Site Name'] = current_site
                all_data.append(temp_df)
                i = j - 1
            i += 1

        if all_data:
            df = pd.concat(all_data, ignore_index=True)

            cols = {
                'subrack': 'Subrack No.',
                'slot': 'Slot No.',
                'port': 'Port No.',
                'tx': 'TX optical power(0.1microwatt)',
                'rx': 'RX optical power(0.1microwatt)'
            }

            if all(c in df.columns for c in cols.values()):
                df['TX_dBm'] = df[cols['tx']].apply(microwatt_to_dbm)
                df['RX_dBm'] = df[cols['rx']].apply(microwatt_to_dbm)

                active_sfp = df[df['TX_dBm'] > -90].copy()
                active_sfp['Attenuation'] = round(active_sfp['TX_dBm'] - active_sfp['RX_dBm'], 2)

                st.header("Анализ по БС и секторам")

                sites = sorted(active_sfp['Site Name'].unique())
                selected_sites = st.multiselect("Выберите БС (Site Name) для отображения", sites, default=sites)

                sectors = sorted(active_sfp[cols['subrack']].unique())
                selected_sector = st.multiselect("Выберите Subrack No. для отображения", sectors, default=sectors)

                filtered_df = active_sfp[
                    (active_sfp['Site Name'].isin(selected_sites)) & 
                    (active_sfp[cols['subrack']].isin(selected_sector))
                ]

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего активных SFP", len(filtered_df))
                with col2:
                    avg_rx = filtered_df['RX_dBm'].mean() if not filtered_df.empty else 0
                    st.metric("Средний прием (RX)", f"{avg_rx:.2f} dBm")
                with col3:
                    critical = len(filtered_df[filtered_df['RX_dBm'] < -8])
                    st.metric("Критические линки (<-8dBm)", critical)

                st.subheader("Детальные данные")

                def color_attenuation(val):
                    if val > 8: return 'background-color: #ff4b4b; color: white' 
                    if val > 5: return 'background-color: #ffa500'
                    return '' 

                display_cols = ['Site Name', cols['subrack'], cols['slot'], cols['port'], 'TX_dBm', 'RX_dBm', 'Attenuation']
                
                styled_df = filtered_df[display_cols].style\
                    .applymap(color_attenuation, subset=['Attenuation'])

                st.dataframe(styled_df, use_container_width=True)

            else:
                st.error("Не удалось найти все необходимые колонки (Subrack, TX, RX).")
        else:
            st.warning("В файле не найдено подходящих данных.")

    except Exception as e:
        st.error(f"Ошибка: {e}")
