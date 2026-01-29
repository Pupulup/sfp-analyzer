import streamlit as st
import pandas as pd
import numpy as np
import re
import csv

def microwatt_to_dbm(val):
    try:
        s_val = str(val).replace('"', '').replace('=', '').strip()
        if s_val.lower() in ['invalid', 'null', 'nan', '']:
            return -99.0
        num = pd.to_numeric(s_val, errors='coerce')
        if pd.isna(num) or num <= 0:
            return -99.0
        mw = (num * 0.1) / 1000
        return round(10 * np.log10(mw), 2)
    except:
        return -99.0

st.set_page_config(page_title="Universal SFP Analyzer", layout="wide")
st.title("Анализ оптики")

uploaded_file = st.file_uploader("Загрузите CSV отчет (DSP SFP + LST RRUCHAIN)", type="csv")

if uploaded_file:
    try:
        raw_bytes = uploaded_file.getvalue()
        try:
            content = raw_bytes.decode('utf-8')
        except:
            content = raw_bytes.decode('utf-16', errors='replace')

        lines = content.splitlines()
        all_rows = []
        current_site = "Unknown_Site"
        headers = None

        for line in lines:
            line_raw = line.rstrip()
            line_clean = line_raw.replace('"', '').strip()

            site_match = re.search(r'(78_[A-Za-z0-9_]+)', line_clean)
            if site_match:
                current_site = site_match.group(1)

            if "Cabinet No." in line_clean and "TX optical power" in line_clean:
                reader = csv.reader([line_raw])
                headers = [h.strip().replace('"', '') for h in next(reader)]
                continue

            if headers:
                if line_clean.startswith("RETCODE") or line_clean.startswith("---") or "END" in line_clean:
                    headers = None
                    continue

                if not line_clean:
                    continue

                reader = csv.reader([line_raw])
                row_values = next(reader)

                if len(row_values) < len(headers):
                    continue

                first_val = row_values[0].replace('"', '').strip()
                if not re.fullmatch(r'\d+', first_val):
                    continue

                row_dict = {}
                for i in range(len(headers)):
                    row_dict[headers[i]] = row_values[i].strip().replace('"', '')

                row_dict['Site Name'] = current_site
                all_rows.append(row_dict)

        if all_rows:
            df = pd.DataFrame(all_rows)

            col_tx = next((c for c in df.columns if "TX optical power(0.1microwatt)" in c), None)
            col_rx = next((c for c in df.columns if "RX optical power(0.1microwatt)" in c), None)
            col_sub = next((c for c in df.columns if "Subrack No" in c), "Subrack No.")
            col_slot = next((c for c in df.columns if "Slot No" in c), "Slot No.")
            col_port = next((c for c in df.columns if "Port No" in c), "Port No.")

            if col_tx and col_rx:
                df['TX_dBm'] = df[col_tx].apply(microwatt_to_dbm)
                df['RX_dBm'] = df[col_rx].apply(microwatt_to_dbm)

                df_active = df[(df['TX_dBm'] > -90) | (df['RX_dBm'] > -90)].copy()
                df_active['Attenuation'] = round(df_active['TX_dBm'] - df_active['RX_dBm'], 2)


                all_sites = sorted(df_active['Site Name'].unique())
                sel_sites = st.multiselect("Фильтр по БС", all_sites, default=all_sites)
                filtered_df = df_active[df_active['Site Name'].isin(sel_sites)]

                st.subheader("Детальный отчет")

                def highlight_vals(row):
                    styles = [''] * len(row)
                    try:
                        i = row.index.get_loc('Attenuation')
                        v = row.iloc[i]
                        if v > 4:
                            styles[i] = 'background-color: #ff4b4b; color: white'
                        elif v > 3.5:
                            styles[i] = 'background-color: #ffa500'
                    except:
                        pass
                    return styles

                show_cols = ['Site Name', col_sub, col_slot, col_port, 'TX_dBm', 'RX_dBm', 'Attenuation']
                st.dataframe(filtered_df[show_cols].style.apply(highlight_vals, axis=1), use_container_width=True)

            else:
                st.error("Колонки мощности не найдены в таблице.")
        else:
            st.warning("Данные не найдены. Возможно, в файле нет секции 'DSP SFP' или заголовки отличаются.")

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
