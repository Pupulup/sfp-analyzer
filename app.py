import streamlit as st
import pandas as pd
import numpy as np
import io

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
st.title("📡 Анализ оптических затуханий")

uploaded_file = st.file_uploader("Загрузите CSV отчет", type="csv")

if uploaded_file:
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        lines = content.splitlines()
        start_line = 0
        for i, line in enumerate(lines):
            if "Cabinet No." in line and "TX optical power" in line:
                start_line = i
                break
                
        data_io = io.StringIO("\n".join(lines[start_line:]))
        df = pd.read_csv(data_io, quotechar='"', skipinitialspace=True)
        df.columns = [c.strip().replace('"', '') for c in df.columns]

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

            st.header("Анализ по секторам")

            sectors = sorted(active_sfp[cols['subrack']].unique())
            selected_sector = st.multiselect("Выберите Subrack No. для отображения", sectors, default=sectors)

            filtered_df = active_sfp[active_sfp[cols['subrack']].isin(selected_sector)]

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

            display_cols = [cols['subrack'], cols['slot'], cols['port'], 'TX_dBm', 'RX_dBm', 'Attenuation']
            
            styled_df = filtered_df[display_cols].style\
                .applymap(color_attenuation, subset=['Attenuation'])

            st.dataframe(styled_df, use_container_width=True)

        else:
            st.error("Не удалось найти все необходимые колонки (Subrack, TX, RX).")

    except Exception as e:
        st.error(f"Ошибка: {e}")
