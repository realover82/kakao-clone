import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import warnings
import numpy as np

warnings.filterwarnings('ignore')

# SQLite 연결 함수
@st.cache_resource
def get_connection():
    try:
        db_path = "./db/SJ_TM2360E_v2.sqlite3"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"데이터베이스 연결에 실패했습니다: {e}")
        return None

# 데이터베이스에서 테이블을 읽어 DataFrame으로 반환하는 함수
def read_data_from_db(conn, table_name):
    try:
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"테이블 '{table_name}'에서 데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None

# analyze_data 함수
# jig_col_name을 인자로 받아 해당 컬럼으로 그룹핑을 수행합니다.
def analyze_data(df, date_col_name, jig_col_name):
    # PassStatusNorm 컬럼 생성
    df['PassStatusNorm'] = ""
    if 'PcbPass' in df.columns:
        df['PassStatusNorm'] = df['PcbPass'].fillna('').astype(str).str.strip().str.upper()
    elif 'FwPass' in df.columns:
        df['PassStatusNorm'] = df['FwPass'].fillna('').astype(str).str.strip().str.upper()
    elif 'RfTxPass' in df.columns:
        df['PassStatusNorm'] = df['RfTxPass'].fillna('').astype(str).str.strip().str.upper()
    elif 'SemiAssyPass' in df.columns:
        df['PassStatusNorm'] = df['SemiAssyPass'].fillna('').astype(str).str.strip().str.upper()
    elif 'BatadcPass' in df.columns:
        df['PassStatusNorm'] = df['BatadcPass'].fillna('').astype(str).str.strip().str.upper()

    summary_data = {}
    all_dates = []

    if jig_col_name not in df.columns or df[jig_col_name].isnull().all():
        st.warning(f"경고: '{jig_col_name}' 필드가 데이터에 없거나 비어 있습니다. 'SNumber' 필드로 대체하여 분석합니다.")
        jig_col_name = 'SNumber'

    if 'SNumber' in df.columns and date_col_name in df.columns and not df[date_col_name].dt.date.dropna().empty:
        for jig, group in df.groupby(jig_col_name):
            for d, day_group in group.groupby(group[date_col_name].dt.date):
                if pd.isna(d): continue
                date_iso = pd.to_datetime(d).strftime("%Y-%m-%d")
                
                pass_sns_series = day_group.groupby('SNumber')['PassStatusNorm'].apply(lambda x: 'O' in x.tolist())
                pass_sns = pass_sns_series[pass_sns_series].index.tolist()

                false_defect_count = len(day_group[(day_group['PassStatusNorm'] == 'X') & (day_group['SNumber'].isin(pass_sns))]['SNumber'].unique())
                true_defect_count = len(day_group[(day_group['PassStatusNorm'] == 'X') & (~day_group['SNumber'].isin(pass_sns))]['SNumber'].unique())
                pass_count = len(pass_sns)
                total_test = len(day_group['SNumber'].unique())
                fail_count = total_test - pass_count

                if jig not in summary_data:
                    summary_data[jig] = {}
                summary_data[jig][date_iso] = {
                    'total_test': total_test,
                    'pass': pass_count,
                    'false_defect': false_defect_count,
                    'true_defect': true_defect_count,
                    'fail': fail_count,
                }
        all_dates = sorted(list(df[date_col_name].dt.date.dropna().unique()))
    
    return summary_data, all_dates

def display_analysis_result(analysis_key, table_name, date_col_name, jig_col_name, selected_jig):
    if st.session_state.analysis_results[analysis_key].empty:
        st.warning("선택한 날짜에 해당하는 분석 데이터가 없습니다.")
        return

    summary_data, all_dates = st.session_state.analysis_data[analysis_key]
    
    if not summary_data:
        st.warning("선택한 날짜에 해당하는 분석 데이터가 없습니다.")
        return

    st.markdown(f"### '{table_name}' 분석 리포트 - {selected_jig}")
    
    kor_date_cols = [f"{d.strftime('%y%m%d')}" for d in all_dates]
    
    st.write(f"**분석 시간**: {st.session_state.analysis_time[analysis_key]}")
    st.markdown("---")

    all_reports_text = ""
    
    jig = selected_jig
    if jig in summary_data:
        st.subheader(f"구분: {jig}")
        
        report_data = {
            '지표': ['총 테스트 수', 'PASS', '가성불량', '진성불량', 'FAIL']
        }
        
        for date_iso, date_str in zip([d.strftime('%Y-%m-%d') for d in all_dates], kor_date_cols):
            data_point = summary_data[jig].get(date_iso)
            if data_point:
                report_data[date_str] = [
                    data_point['total_test'],
                    data_point['pass'],
                    data_point['false_defect'],
                    data_point['true_defect'],
                    data_point['fail']
                ]
            else:
                report_data[date_str] = ['N/A'] * 5
        
        report_df = pd.DataFrame(report_data)
        st.table(report_df)
        all_reports_text += report_df.to_csv(index=False) + "\n"
    else:
        st.warning("선택된 PC에 대한 분석 데이터가 없습니다.")
    
    st.success("분석 완료! 결과가 저장되었습니다.")

    st.download_button(
        label="분석 결과 다운로드",
        data=all_reports_text.encode('utf-8-sig'),
        file_name=f"{table_name}_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


def main():
    st.set_page_config(layout="wide")
    st.title("리모컨 생산 데이터 분석 툴")
    st.markdown("---")

    conn = get_connection()
    if conn is None:
        return

    # 세션 상태 변수 초기화
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = {'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None}
    if 'analysis_data' not in st.session_state:
        st.session_state.analysis_data = {'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None}
    if 'analysis_time' not in st.session_state:
        st.session_state.analysis_time = {'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None}
    
    try:
        df_all_data = pd.read_sql_query("SELECT * FROM historyinspection;", conn)
    except Exception as e:
        st.error(f"데이터베이스에서 'historyinspection' 테이블을 불러오는 중 오류가 발생했습니다: {e}")
        return

    # 모든 날짜 관련 컬럼을 datetime 객체로 미리 변환
    df_all_data['PcbStartTime_dt'] = pd.to_datetime(df_all_data['PcbStartTime'], errors='coerce')
    df_all_data['FwStamp_dt'] = pd.to_datetime(df_all_data['FwStamp'], errors='coerce')
    df_all_data['RfTxStamp_dt'] = pd.to_datetime(df_all_data['RfTxStamp'], errors='coerce')
    df_all_data['SemiAssyStartTime_dt'] = pd.to_datetime(df_all_data['SemiAssyStartTime'], errors='coerce')
    df_all_data['BatadcStamp_dt'] = pd.to_datetime(df_all_data['BatadcStamp'], errors='coerce')

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["파일 PCB 분석", "파일 Fw 분석", "파일 RfTx 분석", "파일 Semi 분석", "파일 Func 분석"])
    
    try:
        with tab1:
            st.header("파일 PCB (Pcb_Process)")
            # 필터링 UI
            col_search, col_date, col_button = st.columns([0.4, 0.4, 0.2])
            with col_search:
                search_query = st.text_input("SNumber 검색", key="search_pcb")
            with col_date:
                df_dates = df_all_data['PcbStartTime_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_pcb")
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_pcb"):
                    with st.spinner("데이터 필터링 및 분석 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['PcbStartTime_dt'].dt.date >= start_date) &
                                (df_all_data['PcbStartTime_dt'].dt.date <= end_date)
                            ].copy()
                            if search_query:
                                df_filtered = df_filtered[df_filtered['SNumber'].str.contains(search_query, case=False, na=False)]
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()
                        
                        st.subheader("---")
                        st.subheader("### 조회된 데이터베이스 내용")
                        st.dataframe(df_filtered)

                        st.session_state.analysis_results['pcb'] = df_filtered
                        st.session_state.analysis_data['pcb'] = analyze_data(df_filtered, 'PcbStartTime_dt', 'PcbMaxIrPwr')
                        st.session_state.analysis_time['pcb'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")
            
            if st.session_state.analysis_results['pcb'] is not None:
                # PC (지그) 목록 버튼 추가
                jig_col = 'PcbMaxIrPwr' if 'PcbMaxIrPwr' in st.session_state.analysis_results['pcb'].columns else 'SNumber'
                jigs = sorted(st.session_state.analysis_results['pcb'][jig_col].dropna().unique())
                if jigs:
                    selected_jig = st.selectbox("PC(지그) 선택", options=jigs, key="select_jig_pcb")
                    display_analysis_result('pcb', 'Pcb_Process', 'PcbStartTime_dt', jig_col, selected_jig)
                else:
                    st.warning("선택 가능한 PC(지그)가 없습니다.")

        with tab2:
            st.header("파일 Fw (Fw_Process)")
            # 필터링 UI
            col_search, col_date, col_button = st.columns([0.4, 0.4, 0.2])
            with col_search:
                search_query = st.text_input("SNumber 검색", key="search_fw")
            with col_date:
                df_dates = df_all_data['FwStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_fw")
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_fw"):
                    with st.spinner("데이터 필터링 및 분석 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['FwStamp_dt'].dt.date >= start_date) &
                                (df_all_data['FwStamp_dt'].dt.date <= end_date)
                            ].copy()
                            if search_query:
                                df_filtered = df_filtered[df_filtered['SNumber'].str.contains(search_query, case=False, na=False)]
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.subheader("---")
                        st.subheader("### 조회된 데이터베이스 내용")
                        st.dataframe(df_filtered)

                        st.session_state.analysis_results['fw'] = df_filtered
                        st.session_state.analysis_data['fw'] = analyze_data(df_filtered, 'FwStamp_dt', 'FwPC')
                        st.session_state.analysis_time['fw'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")

            if st.session_state.analysis_results['fw'] is not None:
                # PC (지그) 목록 버튼 추가
                jig_col = 'FwPC' if 'FwPC' in st.session_state.analysis_results['fw'].columns else 'SNumber'
                jigs = sorted(st.session_state.analysis_results['fw'][jig_col].dropna().unique())
                if jigs:
                    selected_jig = st.selectbox("PC(지그) 선택", options=jigs, key="select_jig_fw")
                    display_analysis_result('fw', 'Fw_Process', 'FwStamp_dt', jig_col, selected_jig)
                else:
                    st.warning("선택 가능한 PC(지그)가 없습니다.")

        with tab3:
            st.header("파일 RfTx (RfTx_Process)")
            # 필터링 UI
            col_search, col_date, col_button = st.columns([0.4, 0.4, 0.2])
            with col_search:
                search_query = st.text_input("SNumber 검색", key="search_rftx")
            with col_date:
                df_dates = df_all_data['RfTxStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_rftx")
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_rftx"):
                    with st.spinner("데이터 필터링 및 분석 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['RfTxStamp_dt'].dt.date >= start_date) &
                                (df_all_data['RfTxStamp_dt'].dt.date <= end_date)
                            ].copy()
                            if search_query:
                                df_filtered = df_filtered[df_filtered['SNumber'].str.contains(search_query, case=False, na=False)]
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.subheader("---")
                        st.subheader("### 조회된 데이터베이스 내용")
                        st.dataframe(df_filtered)

                        st.session_state.analysis_results['rftx'] = df_filtered
                        st.session_state.analysis_data['rftx'] = analyze_data(df_filtered, 'RfTxStamp_dt', 'RfTxPC')
                        st.session_state.analysis_time['rftx'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")

            if st.session_state.analysis_results['rftx'] is not None:
                # PC (지그) 목록 버튼 추가
                jig_col = 'RfTxPC' if 'RfTxPC' in st.session_state.analysis_results['rftx'].columns else 'SNumber'
                jigs = sorted(st.session_state.analysis_results['rftx'][jig_col].dropna().unique())
                if jigs:
                    selected_jig = st.selectbox("PC(지그) 선택", options=jigs, key="select_jig_rftx")
                    display_analysis_result('rftx', 'RfTx_Process', 'RfTxStamp_dt', jig_col, selected_jig)
                else:
                    st.warning("선택 가능한 PC(지그)가 없습니다.")

        with tab4:
            st.header("파일 Semi (SemiAssy_Process)")
            # 필터링 UI
            col_search, col_date, col_button = st.columns([0.4, 0.4, 0.2])
            with col_search:
                search_query = st.text_input("SNumber 검색", key="search_semi")
            with col_date:
                df_dates = df_all_data['SemiAssyStartTime_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_semi")
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_semi"):
                    with st.spinner("데이터 필터링 및 분석 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['SemiAssyStartTime_dt'].dt.date >= start_date) &
                                (df_all_data['SemiAssyStartTime_dt'].dt.date <= end_date)
                            ].copy()
                            if search_query:
                                df_filtered = df_filtered[df_filtered['SNumber'].str.contains(search_query, case=False, na=False)]
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.subheader("---")
                        st.subheader("### 조회된 데이터베이스 내용")
                        st.dataframe(df_filtered)

                        st.session_state.analysis_results['semi'] = df_filtered
                        st.session_state.analysis_data['semi'] = analyze_data(df_filtered, 'SemiAssyStartTime_dt', 'SemiAssyMaxBatVolt')
                        st.session_state.analysis_time['semi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")

            if st.session_state.analysis_results['semi'] is not None:
                # PC (지그) 목록 버튼 추가
                jig_col = 'SemiAssyMaxBatVolt' if 'SemiAssyMaxBatVolt' in st.session_state.analysis_results['semi'].columns else 'SNumber'
                jigs = sorted(st.session_state.analysis_results['semi'][jig_col].dropna().unique())
                if jigs:
                    selected_jig = st.selectbox("PC(지그) 선택", options=jigs, key="select_jig_semi")
                    display_analysis_result('semi', 'SemiAssy_Process', 'SemiAssyStartTime_dt', jig_col, selected_jig)
                else:
                    st.warning("선택 가능한 PC(지그)가 없습니다.")

        with tab5:
            st.header("파일 Func (Func_Process)")
            # 필터링 UI
            col_search, col_date, col_button = st.columns([0.4, 0.4, 0.2])
            with col_search:
                search_query = st.text_input("SNumber 검색", key="search_func")
            with col_date:
                df_dates = df_all_data['BatadcStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_func")
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_func"):
                    with st.spinner("데이터 필터링 및 분석 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['BatadcStamp_dt'].dt.date >= start_date) &
                                (df_all_data['BatadcStamp_dt'].dt.date <= end_date)
                            ].copy()
                            if search_query:
                                df_filtered = df_filtered[df_filtered['SNumber'].str.contains(search_query, case=False, na=False)]
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()
                        
                        st.subheader("---")
                        st.subheader("### 조회된 데이터베이스 내용")
                        st.dataframe(df_filtered)
                        
                        st.session_state.analysis_results['func'] = df_filtered
                        st.session_state.analysis_data['func'] = analyze_data(df_filtered, 'BatadcStamp_dt', 'BatadcPC')
                        st.session_state.analysis_time['func'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")
            
            if st.session_state.analysis_results['func'] is not None:
                # PC (지그) 목록 버튼 추가
                jig_col = 'BatadcPC' if 'BatadcPC' in st.session_state.analysis_results['func'].columns else 'SNumber'
                jigs = sorted(st.session_state.analysis_results['func'][jig_col].dropna().unique())
                if jigs:
                    selected_jig = st.selectbox("PC(지그) 선택", options=jigs, key="select_jig_func")
                    display_analysis_result('func', 'Func_Process', 'BatadcStamp_dt', jig_col, selected_jig)
                else:
                    st.warning("선택 가능한 PC(지그)가 없습니다.")

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
