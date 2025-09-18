import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# SQLite 연결 함수
@st.cache_resource
def get_connection():
    try:
        db_path = "db/SJ_TM2360E_v2.sqlite3"
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
def analyze_data(df, date_col_name):
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

    jig_col = 'SNumber'
    if 'PcbMaxIrPwr' in df.columns and not df['PcbMaxIrPwr'].isnull().all():
        jig_col = 'PcbMaxIrPwr'
    if 'BatadcStamp' in df.columns and not df['BatadcStamp'].isnull().all():
        jig_col = 'BatadcStamp'
    
    if 'SNumber' in df.columns and date_col_name in df.columns and not df[date_col_name].dt.date.dropna().empty:
        for jig, group in df.groupby(jig_col):
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


# display_analysis_result 함수 수정
def display_analysis_result(analysis_key, table_name, date_col_name, selected_jig=None):
    if st.session_state.analysis_results[analysis_key].empty:
        st.warning("선택한 날짜에 해당하는 분석 데이터가 없습니다.")
        return

    summary_data, all_dates = st.session_state.analysis_data[analysis_key]
    
    if not summary_data:
        st.warning("선택한 날짜에 해당하는 분석 데이터가 없습니다.")
        return

    st.markdown(f"### '{table_name}' 분석 리포트")
    
    # 선택된 jig에 따라 데이터 필터링
    jigs_to_display = [selected_jig] if selected_jig and selected_jig in summary_data else sorted(summary_data.keys())

    if not jigs_to_display:
        st.warning("선택한 PC (Jig)에 대한 데이터가 없습니다.")
        return
        
    kor_date_cols = [f"{d.strftime('%y%m%d')}" for d in all_dates]
    
    st.write(f"**분석 시간**: {st.session_state.analysis_time[analysis_key]}")
    st.markdown("---")

    all_reports_text = ""
    
    for jig in jigs_to_display:
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

    # 세션 상태 초기화
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = {
            'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None
        }
    if 'analysis_data' not in st.session_state:
        st.session_state.analysis_data = {
            'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None
        }
    if 'analysis_time' not in st.session_state:
        st.session_state.analysis_time = {
            'pcb': None, 'fw': None, 'rftx': None, 'semi': None, 'func': None
        }
    
    try:
        # 모든 탭에서 공통으로 사용할 원본 데이터를 한 번만 불러옵니다.
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

    # --- 통합 검색 기능 ---
    st.markdown("### 통합 검색")
    search_query = st.text_input("검색어를 입력하세요 (예: 240531, 100000001 등)", key="search_bar")
    
    if st.button("통합 검색 실행", key="global_search_btn"):
        if search_query:
            with st.spinner("전체 데이터에서 검색 중..."):
                # 모든 컬럼을 문자열로 변환하고 검색어를 포함하는 행 찾기
                search_df = df_all_data.astype(str)
                filtered_df = search_df[search_df.apply(
                    lambda row: row.str.contains(search_query, case=False, na=False).any(),
                    axis=1
                )]
            
            if not filtered_df.empty:
                st.success(f"'{search_query}'에 대한 {len(filtered_df)}건의 검색 결과를 찾았습니다.")
                st.dataframe(filtered_df.reset_index(drop=True))
            else:
                st.warning(f"'{search_query}'에 대한 검색 결과가 없습니다.")
    st.markdown("---")

    # --- 탭별 분석 및 조회 기능 ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["파일 PCB 분석", "파일 Fw 분석", "파일 RfTx 분석", "파일 Semi 분석", "파일 Func 분석"])
    
    try:
        with tab1:
            st.header("파일 PCB (Pcb_Process)")
            
            # PC (Jig) 선택 기능 추가
            unique_pc_pcb = df_all_data['PcbMaxIrPwr'].dropna().unique()
            pc_options_pcb = ['모든 PC'] + list(unique_pc_pcb)
            selected_pc_pcb = st.selectbox("PC (Jig) 선택", pc_options_pcb, key="pc_select_pcb")

            col_date, col_button, col_view = st.columns([0.6, 0.2, 0.2])
            with col_date:
                df_dates = df_all_data['PcbStartTime_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_pcb")
            
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_pcb"):
                    with st.spinner("데이터 분석 및 저장 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['PcbStartTime_dt'].dt.date >= start_date) &
                                (df_all_data['PcbStartTime_dt'].dt.date <= end_date)
                            ].copy()
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()
                        
                        st.session_state.analysis_results['pcb'] = df_filtered
                        st.session_state.analysis_data['pcb'] = analyze_data(df_filtered, 'PcbStartTime_dt')
                        st.session_state.analysis_time['pcb'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")
            
            with col_view:
                st.markdown("---")
                if st.button("원본 DB 조회", key="view_db_pcb"):
                    if st.session_state.analysis_results['pcb'] is not None:
                        st.dataframe(st.session_state.analysis_results['pcb'].reset_index(drop=True))
                    else:
                        st.warning("분석을 먼저 실행해주세요.")

            if st.session_state.analysis_results['pcb'] is not None:
                display_analysis_result('pcb', 'Pcb_Process', 'PcbStartTime_dt',
                                        selected_jig=selected_pc_pcb if selected_pc_pcb != '모든 PC' else None)

        with tab2:
            st.header("파일 Fw (Fw_Process)")

            unique_pc_fw = df_all_data['PcbMaxIrPwr'].dropna().unique()
            pc_options_fw = ['모든 PC'] + list(unique_pc_fw)
            selected_pc_fw = st.selectbox("PC (Jig) 선택", pc_options_fw, key="pc_select_fw")

            col_date, col_button, col_view = st.columns([0.6, 0.2, 0.2])
            with col_date:
                df_dates = df_all_data['FwStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_fw")
            
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_fw"):
                    with st.spinner("데이터 분석 및 저장 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['FwStamp_dt'].dt.date >= start_date) &
                                (df_all_data['FwStamp_dt'].dt.date <= end_date)
                            ].copy()
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.session_state.analysis_results['fw'] = df_filtered
                        st.session_state.analysis_data['fw'] = analyze_data(df_filtered, 'FwStamp_dt')
                        st.session_state.analysis_time['fw'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")
            
            with col_view:
                st.markdown("---")
                if st.button("원본 DB 조회", key="view_db_fw"):
                    if st.session_state.analysis_results['fw'] is not None:
                        st.dataframe(st.session_state.analysis_results['fw'].reset_index(drop=True))
                    else:
                        st.warning("분석을 먼저 실행해주세요.")

            if st.session_state.analysis_results['fw'] is not None:
                display_analysis_result('fw', 'Fw_Process', 'FwStamp_dt',
                                        selected_jig=selected_pc_fw if selected_pc_fw != '모든 PC' else None)

        with tab3:
            st.header("파일 RfTx (RfTx_Process)")

            unique_pc_rftx = df_all_data['PcbMaxIrPwr'].dropna().unique()
            pc_options_rftx = ['모든 PC'] + list(unique_pc_rftx)
            selected_pc_rftx = st.selectbox("PC (Jig) 선택", pc_options_rftx, key="pc_select_rftx")

            col_date, col_button, col_view = st.columns([0.6, 0.2, 0.2])
            with col_date:
                df_dates = df_all_data['RfTxStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_rftx")
            
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_rftx"):
                    with st.spinner("데이터 분석 및 저장 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['RfTxStamp_dt'].dt.date >= start_date) &
                                (df_all_data['RfTxStamp_dt'].dt.date <= end_date)
                            ].copy()
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.session_state.analysis_results['rftx'] = df_filtered
                        st.session_state.analysis_data['rftx'] = analyze_data(df_filtered, 'RfTxStamp_dt')
                        st.session_state.analysis_time['rftx'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")

            with col_view:
                st.markdown("---")
                if st.button("원본 DB 조회", key="view_db_rftx"):
                    if st.session_state.analysis_results['rftx'] is not None:
                        st.dataframe(st.session_state.analysis_results['rftx'].reset_index(drop=True))
                    else:
                        st.warning("분석을 먼저 실행해주세요.")

            if st.session_state.analysis_results['rftx'] is not None:
                display_analysis_result('rftx', 'RfTx_Process', 'RfTxStamp_dt',
                                        selected_jig=selected_pc_rftx if selected_pc_rftx != '모든 PC' else None)

        with tab4:
            st.header("파일 Semi (SemiAssy_Process)")

            unique_pc_semi = df_all_data['PcbMaxIrPwr'].dropna().unique()
            pc_options_semi = ['모든 PC'] + list(unique_pc_semi)
            selected_pc_semi = st.selectbox("PC (Jig) 선택", pc_options_semi, key="pc_select_semi")

            col_date, col_button, col_view = st.columns([0.6, 0.2, 0.2])
            with col_date:
                df_dates = df_all_data['SemiAssyStartTime_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_semi")
            
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_semi"):
                    with st.spinner("데이터 분석 및 저장 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['SemiAssyStartTime_dt'].dt.date >= start_date) &
                                (df_all_data['SemiAssyStartTime_dt'].dt.date <= end_date)
                            ].copy()
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()

                        st.session_state.analysis_results['semi'] = df_filtered
                        st.session_state.analysis_data['semi'] = analyze_data(df_filtered, 'SemiAssyStartTime_dt')
                        st.session_state.analysis_time['semi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")

            with col_view:
                st.markdown("---")
                if st.button("원본 DB 조회", key="view_db_semi"):
                    if st.session_state.analysis_results['semi'] is not None:
                        st.dataframe(st.session_state.analysis_results['semi'].reset_index(drop=True))
                    else:
                        st.warning("분석을 먼저 실행해주세요.")

            if st.session_state.analysis_results['semi'] is not None:
                display_analysis_result('semi', 'SemiAssy_Process', 'SemiAssyStartTime_dt',
                                        selected_jig=selected_pc_semi if selected_pc_semi != '모든 PC' else None)

        with tab5:
            st.header("파일 Func (Func_Process)")

            unique_pc_func = df_all_data['PcbMaxIrPwr'].dropna().unique()
            pc_options_func = ['모든 PC'] + list(unique_pc_func)
            selected_pc_func = st.selectbox("PC (Jig) 선택", pc_options_func, key="pc_select_func")
            
            col_date, col_button, col_view = st.columns([0.6, 0.2, 0.2])
            with col_date:
                df_dates = df_all_data['BatadcStamp_dt'].dt.date.dropna()
                min_date = df_dates.min() if not df_dates.empty else date.today()
                max_date = df_dates.max() if not df_dates.dropna().empty else date.today()
                selected_dates = st.date_input("날짜 범위 선택", value=(min_date, max_date), key="dates_func")
            
            with col_button:
                st.markdown("---")
                if st.button("분석 실행", key="analyze_func"):
                    with st.spinner("데이터 분석 및 저장 중..."):
                        if len(selected_dates) == 2:
                            start_date, end_date = selected_dates
                            df_filtered = df_all_data[
                                (df_all_data['BatadcStamp_dt'].dt.date >= start_date) &
                                (df_all_data['BatadcStamp_dt'].dt.date <= end_date)
                            ].copy()
                        else:
                            st.warning("날짜 범위를 올바르게 선택해주세요.")
                            df_filtered = pd.DataFrame()
                        
                        st.session_state.analysis_results['func'] = df_filtered
                        st.session_state.analysis_data['func'] = analyze_data(df_filtered, 'BatadcStamp_dt')
                        st.session_state.analysis_time['func'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    st.success("분석 완료! 결과가 저장되었습니다.")
            
            with col_view:
                st.markdown("---")
                if st.button("원본 DB 조회", key="view_db_func"):
                    if st.session_state.analysis_results['func'] is not None:
                        st.dataframe(st.session_state.analysis_results['func'].reset_index(drop=True))
                    else:
                        st.warning("분석을 먼저 실행해주세요.")

            if st.session_state.analysis_results['func'] is not None:
                display_analysis_result('func', 'Func_Process', 'BatadcStamp_dt',
                                        selected_jig=selected_pc_func if selected_pc_func != '모든 PC' else None)
    
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
