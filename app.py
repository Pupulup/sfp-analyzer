import streamlit as st
import pandas as pd
import numpy as np
import re
import csv
import io

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

uploaded_file = st.file_uploader("Загрузите CSV отчет (DSP SFP + FAN + RRU)", type="csv")

if uploaded_file:
    try:
        content = uploaded_file.getvalue().decode('utf-8', errors='replace')
        lines = content.splitlines()
        
        all_rows = []
        current_site = "Unknown_Site"
        
        headers = None
        
        for line in lines:
            line_clean = line.strip()
            
            if "78_" in line_clean and "DSP" not in line_clean:
                match = re.search(r'(?:BTS_)?(78_[A-Za-z0-9_]+)', line_clean)
                if match:
                    current_site = match.group(1)

            if "Cabinet No." in line_clean and "TX optical power" in line_clean:
                reader = csv.reader([line_clean], skipinitialspace=True)
                headers = next(reader)
                headers = [h.strip() for h in headers]
                continue 

            if headers:
                if not line_clean or "RETCODE" in line_clean or "---" in line_clean:
                    headers = None
                    continue
                
                try:
                    reader = csv.reader([line_clean], skipinitialspace=True)
                    row_values = next(reader)
                    
                    if len(row_values) >= len(headers) - 5:
                        if row_values[0].strip().isdigit():
                            row_dict = {}
                            for h, v in zip(headers, row_values):
                                row_dict[h] = v
                            
                            row_dict['Site Name'] = current_site
                            all_rows.append(row_dict)
                except:
                    continue

        if all_rows:
            df = pd.DataFrame(all_rows)
            
            col_tx = next((c for c in df.columns if "TX optical power" in c), None)
            col_rx = next((c for c in df.columns if "RX optical power" in c), None)
            col_sub = next((c for c in df.columns if "Subrack No" in c), None)
            col_slot = next((c for c in df.columns if "Slot No" in c), None)
            col_port = next((c for c in df.columns if "Port No" in c), None)

            if col_tx and col_rx:
                df['TX_dBm'] = df[col_tx].apply(microwatt_to_dbm)
                df['RX_dBm'] = df[col_rx].apply(microwatt_to_dbm)
                df_active = df[(df['TX_dBm'] > -90) | (df['RX_dBm'] > -90)].copy()
                df_active['Attenuation'] = df_active['TX_dBm'] - df_active['RX_dBm']
                st.success(f"Обработано строк: {len(df_active)}. Сайтов: {df_active['Site Name'].nunique()}")

                all_sites = sorted(df_active['Site Name'].unique())
                sel_sites = st.multiselect("Фильтр по БС", all_sites, default=all_sites)
                
                filtered_df = df_active[df_active['Site Name'].isin(sel_sites)]

                st.subheader("Детальный отчет")

                def highlight_vals(row):
                    styles = [''] * len(row)
                    idx_rx = row.index.get_loc('RX_dBm')
                    idx_att = row.index.get_loc('Attenuation')
                    
                    rx_val = row.iloc[idx_rx]
                    att_val = row.iloc[idx_att]
                    
                    if att_val > 8: styles[idx_att] = 'background-color: #ff4b4b; color: white'
                    elif att_val > 5: styles[idx_att] = 'background-color: #ffa500'
                    
                    return styles

                show_cols = ['Site Name', col_sub, col_slot, col_port, 'TX_dBm', 'RX_dBm', 'Attenuation']
                
                st.dataframe(
                    filtered_df[show_cols].style.apply(highlight_vals, axis=1),
                    use_container_width=True
                )

            else:
                st.error(f"Не найдены колонки мощности. Доступные колонки: {list(df.columns)}")
                st.write("Пример данных:", df.head(1))
        else:
            st.warning("Данные не найдены. Возможно, в файле нет секции 'DSP SFP' или заголовки отличаются.")
            
    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
