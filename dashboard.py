import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path
from datetime import timedelta

DB_PATH = Path(__file__).parent / "analysis.db"

st.set_page_config(page_title="Garmin Analytics", layout="wide")

# 모바일 반응형 CSS
st.markdown("""
<style>
/* metric 라벨 줄바꿈 허용 */
[data-testid="stMetricLabel"] { white-space: normal !important; word-wrap: break-word; }

/* 모바일에서 metric 컬럼 2개씩 배치 */
@media (max-width: 768px) {
    /* 컬럼 그리드를 2열로 변경 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: 0 0 calc(50% - 0.5rem) !important;
        min-width: calc(50% - 0.5rem) !important;
    }
    /* 탭 폰트 축소 */
    [data-testid="stTab"] button {
        font-size: 0.8rem !important;
        padding: 0.3rem 0.5rem !important;
    }
    /* metric 값 폰트 축소 */
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    /* 커스텀 metric 값 폰트 축소 */
    .custom-metric-value {
        font-size: 1.5rem !important;
    }
    /* metric 라벨 폰트 축소 */
    [data-testid="stMetric"] label {
        font-size: 0.75rem !important;
    }
    /* 사이드바 기본 숨김 (햄버거 메뉴로) */
    [data-testid="stSidebar"] {
        min-width: 0 !important;
    }
}

/* 초소형 화면 (폰 세로) */
@media (max-width: 480px) {
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: 0 0 100% !important;
        min-width: 100% !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    .custom-metric-value {
        font-size: 1.3rem !important;
    }
    h1 {
        font-size: 1.3rem !important;
    }
    h2 {
        font-size: 1.1rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("🏃 GGanghuni's Garmin Analytics Dashboard")


@st.cache_resource
def get_connection():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def safe_load(query):
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn)
    except Exception:
        return pd.DataFrame()


def add_week_columns(df, date_col='activity_date'):
    week_start = df[date_col] - pd.to_timedelta(df[date_col].dt.dayofweek, unit='D')
    df['week_start'] = week_start
    df['week'] = week_start.dt.strftime('%m/%d')
    return df


@st.cache_data(ttl=300)
def load_run_data():
    df = safe_load("SELECT * FROM run_analysis ORDER BY activity_date")
    if 'activity_date' in df.columns:
        df['activity_date'] = pd.to_datetime(df['activity_date'])
        df = add_week_columns(df)
    return df


@st.cache_data(ttl=300)
def load_cycling_data():
    df = safe_load("SELECT * FROM cycling_analysis ORDER BY activity_date")
    if 'activity_date' in df.columns:
        df['activity_date'] = pd.to_datetime(df['activity_date'])
        df = add_week_columns(df)
    return df


@st.cache_data(ttl=300)
def load_health_data():
    df = safe_load("SELECT * FROM daily_health ORDER BY date")
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    return df


def pace_str_to_minutes(pace_str):
    if pd.isna(pace_str) or pace_str is None:
        return None
    try:
        parts = str(pace_str).split(':')
        return int(parts[0]) + int(parts[1]) / 60
    except (ValueError, IndexError):
        return None


def minutes_to_pace_str(minutes):
    if pd.isna(minutes):
        return ""
    m = int(minutes)
    s = round((minutes - m) * 60)
    return f"{m}:{s:02d}"


# ─── 탭 구성 (4개) ────────────────────────────────────────
tab_overview, tab_run, tab_bike, tab_health, tab_ai = st.tabs([
    "📊 Overview", "🏃 Running", "🚴 Cycling", "❤️ Health", "🤖 AI Coach"
])


# ═══════════════════════════════════════════════════════════
# TAB 0: Overview
# ═══════════════════════════════════════════════════════════
with tab_overview:
    run_df = load_run_data()
    cyc_df = load_cycling_data()
    hdf = load_health_data()

    if hdf.empty and run_df.empty and cyc_df.empty:
        st.warning("데이터가 없습니다. 먼저 동기화를 실행하세요.")
    else:
        st.sidebar.header("📊 Overview Filters")
        all_dates = []
        if not run_df.empty:
            all_dates.extend(run_df['activity_date'].dt.date.tolist())
        if not cyc_df.empty:
            all_dates.extend(cyc_df['activity_date'].dt.date.tolist())
        if not hdf.empty:
            all_dates.extend(hdf['date'].dt.date.tolist())

        if all_dates:
            ov_date_min = min(all_dates)
            ov_date_max = max(all_dates)
            ov_range = st.sidebar.date_input("Overview date range",
                value=(max(ov_date_min, ov_date_max - timedelta(days=30)), ov_date_max),
                min_value=ov_date_min, max_value=ov_date_max, key="ov_date")
            if len(ov_range) == 2:
                if not run_df.empty:
                    run_df = run_df[(run_df['activity_date'].dt.date >= ov_range[0]) & (run_df['activity_date'].dt.date <= ov_range[1])]
                if not cyc_df.empty:
                    cyc_df = cyc_df[(cyc_df['activity_date'].dt.date >= ov_range[0]) & (cyc_df['activity_date'].dt.date <= ov_range[1])]
                if not hdf.empty:
                    hdf = hdf[(hdf['date'].dt.date >= ov_range[0]) & (hdf['date'].dt.date <= ov_range[1])]

        # ─── 오늘 상태 (항상 최신 데이터) ─────────────────
        hdf_all = load_health_data()
        if not hdf_all.empty:
            # sleep_score가 있는 최신 행 (빈 데이터 행 제외)
            hdf_valid = hdf_all[hdf_all['sleep_score'].notna()]
            if hdf_valid.empty:
                hdf_valid = hdf_all
            latest = hdf_valid.iloc[-1]
            st.header(f"Latest Status ({str(latest['date'])[:10]})")
            st.caption("가민 워치에서 측정한 최근 신체 상태 요약입니다.")
            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            with c1:
                v = latest.get('training_readiness')
                lv = latest.get('training_readiness_level', '')
                if pd.notna(v):
                    lv_text = f" <span style='font-size:0.85rem;opacity:0.6;font-weight:normal;'>({lv})</span>" if lv else ""
                    st.markdown(f"""<div>
<label style="font-size:0.875rem;font-weight:400;color:white;">Training Readiness</label>
<div class="custom-metric-value" style="font-size:2.25rem;font-weight:700;line-height:1.2;color:white;">{int(v)}{lv_text}</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.metric("Training Readiness", "N/A")
            with c2:
                v = latest.get('sleep_score')
                st.metric("Sleep Score", f"{int(v)}" if pd.notna(v) else "N/A")
            with c3:
                v = latest.get('resting_hr')
                if pd.notna(v):
                    st.markdown(f"""<div>
<label style="font-size:0.875rem;font-weight:400;color:white;">Resting HR</label>
<div class="custom-metric-value" style="font-size:2.25rem;font-weight:700;line-height:1.2;color:white;">{int(v)} <span style='font-size:0.85rem;opacity:0.6;font-weight:normal;'>bpm</span></div>
</div>""", unsafe_allow_html=True)
                else:
                    st.metric("Resting HR", "N/A")
            with c4:
                v = latest.get('body_battery_level')
                st.metric("Battery Level", f"{int(v)}" if pd.notna(v) else "N/A")
            with c5:
                v = latest.get('body_battery_charged')
                st.metric("Battery Charged", f"{int(v)}" if pd.notna(v) else "N/A")
            with c6:
                v = latest.get('avg_stress')
                st.metric("Avg Stress", f"{int(v)}" if pd.notna(v) else "N/A")
            with c7:
                v = latest.get('steps')
                st.metric("Steps", f"{int(v):,}" if pd.notna(v) else "N/A")

            st.divider()

        # ─── 필터 기간 평균 (필터 연동) ──────────────────
        if not hdf.empty:
            date_from = hdf['date'].min().strftime('%m/%d')
            date_to = hdf['date'].max().strftime('%m/%d')
            st.header(f"Period Average ({date_from} ~ {date_to})")
            st.caption("선택한 기간의 평균 지표입니다. 최신값과 비교하여 ▲ 상승 / ▼ 하락을 표시합니다.")

            # latest 값 가져오기 (비교용)
            lt = hdf_all.iloc[-1] if not hdf_all.empty else {}

            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            with c1:
                avg_v = hdf['training_readiness'].mean()
                lt_v = lt.get('training_readiness') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Readiness", f"{avg_v:.0f}" if pd.notna(avg_v) else "N/A", delta=delta)
            with c2:
                avg_v = hdf['sleep_score'].mean()
                lt_v = lt.get('sleep_score') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Sleep", f"{avg_v:.0f}" if pd.notna(avg_v) else "N/A", delta=delta)
            with c3:
                avg_v = hdf['resting_hr'].mean()
                lt_v = lt.get('resting_hr') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Resting HR", f"{avg_v:.0f} bpm" if pd.notna(avg_v) else "N/A",
                          delta=delta, delta_color="inverse")
            with c4:
                avg_v = hdf['body_battery_level'].mean()
                lt_v = lt.get('body_battery_level') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Battery Level", f"{avg_v:.0f}" if pd.notna(avg_v) else "N/A", delta=delta)
            with c5:
                avg_v = hdf['body_battery_charged'].mean()
                lt_v = lt.get('body_battery_charged') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Charged", f"{avg_v:.0f}" if pd.notna(avg_v) else "N/A", delta=delta)
            with c6:
                avg_v = hdf['avg_stress'].mean()
                lt_v = lt.get('avg_stress') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Stress", f"{avg_v:.0f}" if pd.notna(avg_v) else "N/A",
                          delta=delta, delta_color="inverse")
            with c7:
                avg_v = hdf['steps'].mean()
                lt_v = lt.get('steps') if isinstance(lt, pd.Series) else None
                delta = f"{lt_v - avg_v:+,.0f}" if pd.notna(avg_v) and pd.notna(lt_v) else None
                st.metric("Avg Steps", f"{avg_v:,.0f}" if pd.notna(avg_v) else "N/A", delta=delta)

            st.divider()

        # ─── 주간 운동 볼륨 ─────────────────────────────
        st.header("Weekly Training Volume")
        st.caption("주간 러닝(빨강) + 사이클링(파랑) 총 거리입니다. 급격한 증가(주 10% 이상)는 부상 위험이 있으니 점진적으로 늘려가세요.")
        weekly_data = []
        if not run_df.empty:
            rw = run_df.groupby('week_start').agg(run_km=('total_distance_km', 'sum')).reset_index()
            weekly_data.append(rw.set_index('week_start'))
        if not cyc_df.empty:
            cw = cyc_df.groupby('week_start').agg(bike_km=('total_distance_km', 'sum')).reset_index()
            weekly_data.append(cw.set_index('week_start'))

        if weekly_data:
            combined = pd.concat(weekly_data, axis=1).fillna(0).reset_index()
            combined.columns.name = None
            if 'run_km' not in combined.columns:
                combined['run_km'] = 0
            if 'bike_km' not in combined.columns:
                combined['bike_km'] = 0
            combined['run_km'] = combined['run_km'].round(1)
            combined['bike_km'] = combined['bike_km'].round(1)
            combined = combined.sort_values('week_start')
            combined['week'] = combined['week_start'].dt.strftime('%m/%d')

            fig = go.Figure()
            fig.add_trace(go.Bar(x=combined['week'], y=combined['run_km'], name='Running', marker_color='#EF553B'))
            fig.add_trace(go.Bar(x=combined['week'], y=combined['bike_km'], name='Cycling', marker_color='#636EFA'))
            fig.update_layout(barmode='stack', height=400, margin=dict(t=20), yaxis_title="Distance (km)",
                              xaxis=dict(type='category'),
                              legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
            st.plotly_chart(fig, width="stretch")

        # ─── Recovery vs Training (영역 차트 + 히트맵) ───
        if not hdf.empty:
            st.header("Recovery & Training Trend")
            st.caption("왼쪽: 수면 점수와 HRV로 회복 상태를 확인합니다. 오른쪽: 훈련 준비도를 날짜별 색상으로 보여줍니다. 준비도가 낮고 스트레스가 높으면 휴식이 필요합니다.")
            col_rec, col_tr = st.columns(2)

            with col_rec:
                rec_df = hdf[['date', 'sleep_score', 'hrv_ms']].dropna(subset=['sleep_score'])
                if not rec_df.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=rec_df['date'], y=rec_df['sleep_score'], mode='lines',
                        name='Sleep Score', line=dict(color='#636EFA', width=1),
                        fill='tozeroy', fillcolor='rgba(99,110,250,0.15)'
                    ))
                    hrv_valid = rec_df[rec_df['hrv_ms'].notna()]
                    if not hrv_valid.empty:
                        fig.add_trace(go.Scatter(
                            x=hrv_valid['date'], y=hrv_valid['hrv_ms'], mode='lines',
                            name='HRV (ms)', line=dict(color='#00CC96', width=1),
                            fill='tozeroy', fillcolor='rgba(0,204,150,0.1)',
                            yaxis='y2'
                        ))
                    fig.update_layout(
                        height=350, margin=dict(t=30), title="Recovery Indicators",
                        yaxis=dict(title="Sleep Score", range=[0, 100]),
                        yaxis2=dict(title="HRV (ms)", overlaying='y', side='right'),
                        legend=dict(orientation="h", yanchor="top", y=-0.15)
                    )
                    st.plotly_chart(fig, width="stretch")

            with col_tr:
                tr_df = hdf[['date', 'training_readiness', 'avg_stress']].copy()
                tr_valid = tr_df[tr_df['training_readiness'].notna()]
                if not tr_valid.empty:
                    fig = go.Figure()
                    colors = ['#00CC96' if v >= 50 else '#FFA15A' if v >= 30 else '#EF553B'
                              for v in tr_valid['training_readiness']]
                    fig.add_trace(go.Bar(x=tr_valid['date'], y=tr_valid['training_readiness'],
                                         marker_color=colors, name='Readiness'))
                    stress_valid = tr_df[tr_df['avg_stress'].notna()]
                    if not stress_valid.empty:
                        fig.add_trace(go.Scatter(
                            x=stress_valid['date'], y=stress_valid['avg_stress'],
                            mode='lines', name='Avg Stress', line=dict(color='#FFA15A', width=2),
                            yaxis='y2'
                        ))
                    fig.update_layout(
                        height=350, margin=dict(t=30), title="Training Readiness vs Stress",
                        yaxis=dict(title="Readiness", range=[0, 100]),
                        yaxis2=dict(title="Stress", overlaying='y', side='right', range=[0, 100]),
                        legend=dict(orientation="h", yanchor="top", y=-0.15)
                    )
                    st.plotly_chart(fig, width="stretch")

        # ─── VO2 Max 추이 (영역 차트 + 목표선) ──────────
        if not hdf.empty:
            vo2_df = hdf[(hdf['vo2_max_running'].notna()) | (hdf['vo2_max_cycling'].notna())].copy()
            if not vo2_df.empty:
                st.header("VO2 Max Trend")
                st.caption("최대산소섭취량 추이입니다. 숫자가 높을수록 심폐 체력이 좋습니다. 장기적으로 올라가면 체력이 향상되고 있다는 뜻이에요.")
                fig = go.Figure()
                run_v = vo2_df[vo2_df['vo2_max_running'].notna()]
                if not run_v.empty:
                    fig.add_trace(go.Scatter(
                        x=run_v['date'], y=run_v['vo2_max_running'], mode='lines+markers',
                        name='Running', marker=dict(size=5, color='#EF553B'), line=dict(width=1),
                        fill='tozeroy', fillcolor='rgba(239,85,59,0.1)'
                    ))
                cyc_v = vo2_df[vo2_df['vo2_max_cycling'].notna()]
                if not cyc_v.empty:
                    fig.add_trace(go.Scatter(
                        x=cyc_v['date'], y=cyc_v['vo2_max_cycling'], mode='lines+markers',
                        name='Cycling', marker=dict(size=5, color='#636EFA'), line=dict(width=1),
                        fill='tozeroy', fillcolor='rgba(99,110,250,0.1)'
                    ))
                # 목표선 (상위 등급 기준)
                fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Excellent (50)")
                fig.update_yaxes(title_text="VO2 Max")
                fig.update_layout(height=350, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15))
                st.plotly_chart(fig, width="stretch")

        # ─── 총 요약 (전체 기간) ─────────────────────────
        st.divider()
        st.caption("All-Time Summary")
        run_all = load_run_data()
        cyc_all = load_cycling_data()
        run_km = run_all['total_distance_km'].sum() if not run_all.empty else 0
        bike_km = cyc_all['total_distance_km'].sum() if not cyc_all.empty else 0
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Total Runs", len(run_all) if not run_all.empty else 0)
        with c2: st.metric("Run Distance", f"{run_km:.0f} km")
        with c3: st.metric("Total Rides", len(cyc_all) if not cyc_all.empty else 0)
        with c4: st.metric("Bike Distance", f"{bike_km:.0f} km")
        with c5: st.metric("Total Distance", f"{run_km + bike_km:.0f} km")


# ═══════════════════════════════════════════════════════════
# TAB 1: Running Analysis
# ═══════════════════════════════════════════════════════════
with tab_run:
    df = load_run_data()
    if df.empty:
        st.warning("러닝 분석 데이터가 없습니다.")
    else:
        st.sidebar.header("🏃 Running Filters")
        date_min = df['activity_date'].min().date()
        date_max = df['activity_date'].max().date()
        date_range = st.sidebar.date_input("Run date range", value=(max(date_min, date_max - timedelta(days=90)), date_max),
                                           min_value=date_min, max_value=date_max, key="run_date")
        if len(date_range) == 2:
            df = df[(df['activity_date'].dt.date >= date_range[0]) & (df['activity_date'].dt.date <= date_range[1])]

        min_dist = st.sidebar.number_input("Min run distance (km)", min_value=0.0, value=0.0, step=1.0, key="run_dist")
        if min_dist > 0:
            df = df[df['total_distance_km'] >= min_dist]

        if df.empty:
            st.warning("No data for the selected filters.")
        else:
            # Summary
            c1, c2, c3, c4 = st.columns(4)
            z2 = df[(df['zone2_avg_pace_min_km'].notna()) & (df['zone2_ratio'] >= 30)].copy()
            hr = df[df['hr_drift_percent'].notna()].copy()
            with c1: st.metric("Total Runs", len(df))
            with c2: st.metric("Total Distance", f"{df['total_distance_km'].sum():.0f} km")
            with c3:
                if not z2.empty:
                    z2['pace_minutes'] = z2['zone2_avg_pace_min_km'].apply(pace_str_to_minutes)
                    z2 = z2[z2['pace_minutes'].notna()]
                    st.metric("Latest Z2 Pace", z2.iloc[-1]['zone2_avg_pace_min_km'] if not z2.empty else "N/A")
                else:
                    st.metric("Latest Z2 Pace", "N/A")
            with c4:
                avg_d = hr['hr_drift_percent'].mean() if not hr.empty else None
                st.metric("Avg HR Drift", f"{avg_d:.1f}%" if avg_d else "N/A")

            st.divider()

            # 1. Zone2 Pace Trend (산점도 + 추세선 유지)
            st.header("1. Zone2 Pace Trend")
            st.caption("심박수 137-156 bpm 구간에서의 평균 페이스입니다. 숫자가 낮을수록(빠를수록) 유산소 체력이 향상된 것입니다. 빨간 선은 5회 이동평균 추세선입니다.")
            if not z2.empty:
                z2['rolling_avg'] = z2['pace_minutes'].rolling(window=5, min_periods=2).mean()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=z2['activity_date'], y=z2['pace_minutes'], mode='markers',
                    name='Pace', marker=dict(size=8, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{customdata}<extra></extra>',
                    customdata=z2['zone2_avg_pace_min_km']))
                fig.add_trace(go.Scatter(x=z2['activity_date'], y=z2['rolling_avg'], mode='lines',
                    name='5-run avg', line=dict(color='#EF553B', width=2)))
                pace_min, pace_max = z2['pace_minutes'].min(), z2['pace_minutes'].max()
                pad = (pace_max - pace_min) * 0.3 if pace_max > pace_min else 0.5
                fig.update_yaxes(title_text="Pace (min/km)", range=[pace_max + pad, pace_min - pad])
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Zone2 pace data not available.")

            # 2. HR Drift (롤리팝 차트)
            st.header("2. HR Drift")
            st.caption("운동 전반부 대비 후반부 심박수 상승률입니다. 🟢 5% 이하 = 유산소 효율 좋음 | 🟠 5-7% = 보통 | 🔴 7% 이상 = 오버페이스 또는 탈수 주의")
            if not hr.empty:
                colors = ['#00CC96' if v <= 5 else '#FFA15A' if v <= 7 else '#EF553B' for v in hr['hr_drift_percent']]
                fig = go.Figure()
                # 롤리팝 스템 (세로선)
                for idx, row in hr.iterrows():
                    c = '#00CC96' if row['hr_drift_percent'] <= 5 else '#FFA15A' if row['hr_drift_percent'] <= 7 else '#EF553B'
                    fig.add_trace(go.Scatter(
                        x=[row['activity_date'], row['activity_date']], y=[0, row['hr_drift_percent']],
                        mode='lines', line=dict(color=c, width=2), showlegend=False,
                        hoverinfo='skip'
                    ))
                # 롤리팝 헤드 (점)
                fig.add_trace(go.Scatter(
                    x=hr['activity_date'], y=hr['hr_drift_percent'], mode='markers',
                    marker=dict(size=10, color=colors, line=dict(width=1, color='white')),
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>',
                    showlegend=False
                ))
                fig.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5% 기준")
                fig.update_yaxes(title_text="HR Drift (%)")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, width="stretch")

            # 3. Weekly Distance (영역 차트)
            st.header("3. Weekly Distance")
            st.caption("주간 총 러닝 거리입니다. 훈련량을 안정적으로 유지하면서 점진적으로 늘려가는 것이 좋습니다.")
            wd = df[df['total_distance_km'].notna()].copy()
            if not wd.empty:
                weekly = wd.groupby('week_start').agg(total_km=('total_distance_km', 'sum'), runs=('total_distance_km', 'count')).reset_index()
                weekly = weekly.sort_values('week_start')
                weekly['total_km'] = weekly['total_km'].round(1)
                weekly['week'] = weekly['week_start'].dt.strftime('%m/%d')
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=weekly['week'], y=weekly['total_km'], mode='lines+markers',
                    marker=dict(size=7, color='#EF553B'), line=dict(width=2, color='#EF553B'),
                    fill='tozeroy', fillcolor='rgba(239,85,59,0.15)',
                    hovertemplate='%{x}<br>%{y:.1f} km<extra></extra>'
                ))
                fig.update_layout(height=400, margin=dict(t=20), xaxis=dict(type='category'),
                                  yaxis_title="Distance (km)")
                st.plotly_chart(fig, width="stretch")

            # 4. Pace Stability (유지)
            st.header("4. Pace Stability (8km+)")
            st.caption("8km 이상 장거리 러닝에서 1km 구간별 페이스 변동계수(CV)입니다. 7.5% 이하면 안정적인 페이스 유지. 높으면 후반에 페이스가 떨어진다는 뜻입니다.")
            ps = df[df['pace_stability_cv'].notna()].copy()
            if not ps.empty:
                fig = go.Figure(go.Scatter(x=ps['activity_date'], y=ps['pace_stability_cv'], mode='markers+lines',
                    marker=dict(size=8, color='#AB63FA'), line=dict(color='#AB63FA', width=1),
                    hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                    customdata=ps['total_distance_km']))
                fig.add_hline(y=7.5, line_dash="dash", line_color="green", annotation_text="7.5%")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("최근 8km 이상 장거리 러닝 기록이 없습니다.")


# ═══════════════════════════════════════════════════════════
# TAB 2: Cycling Analysis
# ═══════════════════════════════════════════════════════════
with tab_bike:
    cdf = load_cycling_data()
    if cdf.empty:
        st.warning("사이클링 분석 데이터가 없습니다.")
    else:
        st.sidebar.header("🚴 Cycling Filters")
        c_date_min = cdf['activity_date'].min().date()
        c_date_max = cdf['activity_date'].max().date()
        c_date_range = st.sidebar.date_input("Bike date range", value=(max(c_date_min, c_date_max - timedelta(days=90)), c_date_max),
                                              min_value=c_date_min, max_value=c_date_max, key="bike_date")
        if len(c_date_range) == 2:
            cdf = cdf[(cdf['activity_date'].dt.date >= c_date_range[0]) & (cdf['activity_date'].dt.date <= c_date_range[1])]

        min_bike_dist = st.sidebar.number_input("Min ride distance (km)", min_value=0.0, value=0.0, step=5.0, key="bike_dist")
        if min_bike_dist > 0:
            cdf = cdf[cdf['total_distance_km'] >= min_bike_dist]

        if cdf.empty:
            st.warning("No data for the selected filters.")
        else:
            # Summary
            hr_c = cdf[cdf['hr_drift_percent'].notna()].copy()
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Total Rides", len(cdf))
            with c2: st.metric("Total Distance", f"{cdf['total_distance_km'].sum():.0f} km")
            with c3:
                avg_spd = cdf['avg_speed_kmh'].mean() if cdf['avg_speed_kmh'].notna().any() else None
                st.metric("Avg Speed", f"{avg_spd:.1f} km/h" if avg_spd else "N/A")
            with c4:
                avg_d = hr_c['hr_drift_percent'].mean() if not hr_c.empty else None
                st.metric("Avg HR Drift", f"{avg_d:.1f}%" if avg_d else "N/A")

            st.divider()

            # 1. Zone2 Speed Trend (유지)
            st.header("1. Zone2 Speed Trend")
            st.caption("심박수 120-145 bpm 구간에서의 평균 속도입니다. 숫자가 높을수록 유산소 체력이 좋아진 것입니다. 같은 심박에서 더 빨리 달릴 수 있으면 체력이 향상된 것이에요.")
            z2c = cdf[(cdf['zone2_avg_speed_kmh'].notna()) & (cdf['zone2_ratio'] >= 20)].copy()
            if not z2c.empty:
                z2c['rolling_avg'] = z2c['zone2_avg_speed_kmh'].rolling(window=5, min_periods=2).mean()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=z2c['activity_date'], y=z2c['zone2_avg_speed_kmh'], mode='markers',
                    name='Speed', marker=dict(size=8, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f} km/h<extra></extra>'))
                fig.add_trace(go.Scatter(x=z2c['activity_date'], y=z2c['rolling_avg'], mode='lines',
                    name='5-ride avg', line=dict(color='#EF553B', width=2)))
                fig.update_yaxes(title_text="Zone2 Speed (km/h)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Zone2 speed data not available.")

            # 2. HR Drift (롤리팝 차트)
            st.header("2. HR Drift")
            st.caption("라이딩 전반부 대비 후반부 심박수 상승률입니다. 🟢 5% 이하 = 양호 | 🟠 5-7% = 보통 | 🔴 7% 이상 = 탈수/영양부족/피로 주의")
            if not hr_c.empty:
                fig = go.Figure()
                for idx, row in hr_c.iterrows():
                    c = '#00CC96' if row['hr_drift_percent'] <= 5 else '#FFA15A' if row['hr_drift_percent'] <= 7 else '#EF553B'
                    fig.add_trace(go.Scatter(
                        x=[row['activity_date'], row['activity_date']], y=[0, row['hr_drift_percent']],
                        mode='lines', line=dict(color=c, width=2), showlegend=False, hoverinfo='skip'
                    ))
                colors_c = ['#00CC96' if v <= 5 else '#FFA15A' if v <= 7 else '#EF553B' for v in hr_c['hr_drift_percent']]
                fig.add_trace(go.Scatter(
                    x=hr_c['activity_date'], y=hr_c['hr_drift_percent'], mode='markers',
                    marker=dict(size=10, color=colors_c, line=dict(width=1, color='white')),
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>',
                    showlegend=False
                ))
                fig.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5% 기준")
                fig.update_yaxes(title_text="HR Drift (%)")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, width="stretch")

            # 3. Weekly Distance (영역 차트)
            st.header("3. Weekly Distance")
            st.caption("주간 총 라이딩 거리입니다. 꾸준한 주간 볼륨 유지가 체력 향상의 기본입니다.")
            cyc_weekly = cdf.groupby('week_start').agg(total_km=('total_distance_km', 'sum'), rides=('total_distance_km', 'count')).reset_index()
            cyc_weekly = cyc_weekly.sort_values('week_start')
            cyc_weekly['total_km'] = cyc_weekly['total_km'].round(1)
            cyc_weekly['week'] = cyc_weekly['week_start'].dt.strftime('%m/%d')
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=cyc_weekly['week'], y=cyc_weekly['total_km'], mode='lines+markers',
                marker=dict(size=7, color='#636EFA'), line=dict(width=2, color='#636EFA'),
                fill='tozeroy', fillcolor='rgba(99,110,250,0.15)',
                hovertemplate='%{x}<br>%{y:.1f} km<extra></extra>'
            ))
            fig.update_layout(height=400, margin=dict(t=20), xaxis=dict(type='category'),
                              yaxis_title="Distance (km)")
            st.plotly_chart(fig, width="stretch")

            # 4. Avg Speed Trend
            st.header("4. Avg Speed Trend")
            st.caption("라이드별 평균 속도 추이입니다. 바람/코스에 따라 변동이 크니 빨간 추세선(5회 이동평균)을 참고하세요.")
            spd = cdf[cdf['avg_speed_kmh'].notna()].copy()
            if not spd.empty:
                spd['rolling_avg'] = spd['avg_speed_kmh'].rolling(window=5, min_periods=2).mean()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=spd['activity_date'], y=spd['avg_speed_kmh'], mode='markers',
                    name='Avg Speed', marker=dict(size=6, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f} km/h<extra></extra>'))
                fig.add_trace(go.Scatter(x=spd['activity_date'], y=spd['rolling_avg'], mode='lines',
                    name='5-ride avg', line=dict(color='#EF553B', width=2)))
                fig.update_yaxes(title_text="Speed (km/h)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, width="stretch")

            # 5. Power Trend (영역 차트 — Avg vs NP 겹침)
            if 'avg_power' in cdf.columns and cdf['avg_power'].notna().any():
                st.header("5. Power Trend")
                st.caption("Avg Power는 평균 출력, NP(Normalized Power)는 페달링 변동을 보정한 실질 강도입니다. NP가 올라가면 같은 시간에 더 강한 강도로 탈 수 있게 된 것입니다.")
                pwr = cdf[cdf['avg_power'].notna()].copy()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pwr['activity_date'], y=pwr['avg_power'], mode='lines+markers',
                    name='Avg Power', marker=dict(size=5, color='#FFA15A'), line=dict(width=1, color='#FFA15A'),
                    fill='tozeroy', fillcolor='rgba(255,161,90,0.1)',
                    hovertemplate='%{x|%Y-%m-%d}<br>Avg: %{y:.0f}W<extra></extra>'
                ))
                if 'normalized_power' in pwr.columns:
                    np_df = pwr[pwr['normalized_power'].notna()]
                    if not np_df.empty:
                        fig.add_trace(go.Scatter(
                            x=np_df['activity_date'], y=np_df['normalized_power'], mode='lines+markers',
                            name='Normalized Power', marker=dict(size=5, color='#EF553B'), line=dict(width=2, color='#EF553B'),
                            fill='tonexty', fillcolor='rgba(239,85,59,0.08)',
                            hovertemplate='%{x|%Y-%m-%d}<br>NP: %{y:.0f}W<extra></extra>'
                        ))
                fig.update_yaxes(title_text="Power (W)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, width="stretch")

                # 6. Power Zone Distribution (도넛 차트)
                st.header("6. Power Zone Distribution")
                st.caption("라이드별 평균 파워 기준 강도 분류입니다. Z2(지구력) 비중이 높으면 베이스 훈련을 잘 하고 있는 것입니다.")
                pwr_rides = cdf[cdf['avg_power'].notna()].copy()
                if not pwr_rides.empty:
                    def power_zone_label(p):
                        if p < 100: return 'Z1 Recovery'
                        elif p < 150: return 'Z2 Endurance'
                        elif p < 200: return 'Z3 Tempo'
                        elif p < 250: return 'Z4 Threshold'
                        else: return 'Z5+ VO2max'

                    pwr_rides['power_zone'] = pwr_rides['avg_power'].apply(power_zone_label)
                    zone_counts = pwr_rides['power_zone'].value_counts().reset_index()
                    zone_counts.columns = ['zone', 'count']
                    zone_order = ['Z1 Recovery', 'Z2 Endurance', 'Z3 Tempo', 'Z4 Threshold', 'Z5+ VO2max']
                    zone_colors = {
                        'Z1 Recovery': '#00CC96', 'Z2 Endurance': '#636EFA',
                        'Z3 Tempo': '#FFA15A', 'Z4 Threshold': '#EF553B', 'Z5+ VO2max': '#AB63FA'
                    }
                    zone_counts['zone'] = pd.Categorical(zone_counts['zone'], categories=zone_order, ordered=True)
                    zone_counts = zone_counts.sort_values('zone')

                    fig = px.pie(zone_counts, values='count', names='zone', hole=0.5,
                                 color='zone', color_discrete_map=zone_colors)
                    fig.update_traces(textposition='outside', textinfo='label+percent')
                    fig.update_layout(height=400, margin=dict(t=20), showlegend=False)
                    st.plotly_chart(fig, width="stretch")

            # 7. FTP 추정 추이
            if 'normalized_power' in cdf.columns:
                ftp_rides = cdf[(cdf['normalized_power'].notna()) & (cdf['total_duration_sec'] >= 1200)].copy()
                if not ftp_rides.empty:
                    st.header("7. Estimated FTP Trend")
                    st.caption("20분 이상 라이딩의 NP × 0.95로 추정한 FTP입니다. 누적 최고값이 올라가면 체력이 향상된 것입니다.")
                    ftp_rides['est_ftp'] = (ftp_rides['normalized_power'] * 0.95).round(0)
                    # 누적 최고 FTP
                    ftp_rides['best_ftp'] = ftp_rides['est_ftp'].cummax()
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=ftp_rides['activity_date'], y=ftp_rides['est_ftp'], mode='markers',
                        name='라이드별 FTP', marker=dict(size=7, color='#636EFA'),
                        hovertemplate='%{x|%Y-%m-%d}<br>FTP: %{y:.0f}W<br>NP: %{customdata:.0f}W<extra></extra>',
                        customdata=ftp_rides['normalized_power']
                    ))
                    fig.add_trace(go.Scatter(
                        x=ftp_rides['activity_date'], y=ftp_rides['best_ftp'], mode='lines',
                        name='Best FTP', line=dict(color='#EF553B', width=2, dash='dash')
                    ))
                    current_ftp = ftp_rides['best_ftp'].iloc[-1]
                    fig.add_annotation(x=ftp_rides['activity_date'].iloc[-1], y=current_ftp,
                                       text=f"  현재 FTP: {current_ftp:.0f}W", showarrow=False,
                                       xanchor='left', font=dict(color='#EF553B', size=12))
                    fig.update_yaxes(title_text="FTP (W)")
                    fig.update_layout(height=400, margin=dict(t=20),
                                      legend=dict(orientation="h", yanchor="top", y=-0.15))
                    st.plotly_chart(fig, width="stretch")

            # 8. Speed Stability (20km+)
            if 'speed_stability_cv' in cdf.columns:
                ss = cdf[cdf['speed_stability_cv'].notna()].copy()
                if not ss.empty:
                    st.header("8. Speed Stability (20km+)")
                    st.caption("20km 이상 장거리 라이딩에서 5km 구간별 속도 변동계수입니다. 10% 이하면 안정적인 페이싱입니다.")
                    fig = go.Figure(go.Scatter(x=ss['activity_date'], y=ss['speed_stability_cv'],
                        mode='markers+lines', marker=dict(size=8, color='#AB63FA'), line=dict(width=1),
                        hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                        customdata=ss['total_distance_km']))
                    fig.add_hline(y=10, line_dash="dash", line_color="green", annotation_text="10%")
                    fig.update_layout(height=400, margin=dict(t=20))
                    st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════
# TAB 3: Health
# ═══════════════════════════════════════════════════════════
with tab_health:
    hdf = load_health_data()
    if hdf.empty:
        st.warning("건강 데이터가 없습니다. `python scripts/main.py --health`를 실행하세요.")
    else:
        st.sidebar.header("❤️ Health Filters")
        h_min = hdf['date'].min().date()
        h_max = hdf['date'].max().date()
        h_range = st.sidebar.date_input("Health date range", value=(max(h_min, h_max - timedelta(days=30)), h_max),
                                         min_value=h_min, max_value=h_max, key="health_date")
        if len(h_range) == 2:
            hdf = hdf[(hdf['date'].dt.date >= h_range[0]) & (hdf['date'].dt.date <= h_range[1])]

        # 1. Sleep
        st.header("1. Sleep Score")
        st.caption("수면 품질 점수와 7일 이동평균(빨간 선)입니다. 추세가 떨어지면 수면 환경이나 생활 패턴을 점검해 보세요.")
        sleep_df = hdf[hdf['sleep_score'].notna()].copy()
        if not sleep_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sleep_df['date'], y=sleep_df['sleep_score'], mode='markers+lines',
                marker=dict(size=5, color='#636EFA'), line=dict(width=1), name='Score'))
            fig.add_trace(go.Scatter(x=sleep_df['date'],
                y=sleep_df['sleep_score'].rolling(7, min_periods=2).mean(),
                mode='lines', name='7-day avg', line=dict(color='#EF553B', width=2)))
            fig.update_yaxes(range=[0, 100], title_text="Sleep Score")
            fig.update_layout(height=350, margin=dict(t=20),
                              legend=dict(orientation="h", yanchor="top", y=-0.15))
            st.plotly_chart(fig, width="stretch")

        # 2. Resting HR & HRV (이중 축 하나로 합침)
        st.header("2. Resting HR & HRV")
        st.caption("안정시 심박수(빨강)는 낮을수록, HRV(초록)는 높을수록 좋습니다. 안정시 심박이 갑자기 높아지면 피로/질병 신호일 수 있어요.")
        rhr = hdf[hdf['resting_hr'].notna()].copy()
        hrv = hdf[hdf['hrv_ms'].notna()].copy()
        if not rhr.empty or not hrv.empty:
            fig = go.Figure()
            if not rhr.empty:
                fig.add_trace(go.Scatter(
                    x=rhr['date'], y=rhr['resting_hr'], mode='lines+markers',
                    name='Resting HR (bpm)', marker=dict(size=4, color='#EF553B'), line=dict(width=1),
                    hovertemplate='%{x|%Y-%m-%d}<br>HR: %{y} bpm<extra></extra>'
                ))
            if not hrv.empty:
                fig.add_trace(go.Scatter(
                    x=hrv['date'], y=hrv['hrv_ms'], mode='lines+markers',
                    name='HRV (ms)', marker=dict(size=4, color='#00CC96'), line=dict(width=1),
                    yaxis='y2',
                    hovertemplate='%{x|%Y-%m-%d}<br>HRV: %{y} ms<extra></extra>'
                ))
            fig.update_layout(
                height=350, margin=dict(t=20),
                yaxis=dict(title="Resting HR (bpm)"),
                yaxis2=dict(title="HRV (ms)", overlaying='y', side='right'),
                legend=dict(orientation="h", yanchor="top", y=-0.15)
            )
            st.plotly_chart(fig, width="stretch")

        # 3. Stress (영역 차트) & Body Battery (워터폴)
        st.header("3. Stress & Body Battery")
        st.caption("스트레스는 낮을수록 좋고, 바디배터리는 충전(초록)이 소모(빨강)보다 많아야 회복이 충분한 것입니다.")
        col1, col2 = st.columns(2)
        with col1:
            stress = hdf[hdf['avg_stress'].notna()].copy()
            if not stress.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=stress['date'], y=stress['avg_stress'], mode='lines',
                    line=dict(color='#FFA15A', width=1),
                    fill='tozeroy', fillcolor='rgba(255,161,90,0.2)',
                    hovertemplate='%{x|%Y-%m-%d}<br>Stress: %{y}<extra></extra>'
                ))
                fig.add_hline(y=40, line_dash="dash", line_color="gray", annotation_text="보통 (40)")
                fig.update_yaxes(range=[0, 100], title_text="Stress")
                fig.update_layout(height=300, margin=dict(t=30), title="Avg Stress")
                st.plotly_chart(fig, width="stretch")

        with col2:
            bb = hdf[hdf['body_battery_charged'].notna()].copy()
            if not bb.empty:
                fig = go.Figure()
                # 워터폴 스타일: 충전 - 소모 = 순 변화
                bb['net'] = bb['body_battery_charged'].fillna(0) - bb['body_battery_drain'].fillna(0)
                bb_colors = ['#00CC96' if v >= 0 else '#EF553B' for v in bb['net']]
                fig.add_trace(go.Bar(
                    x=bb['date'], y=bb['net'], marker_color=bb_colors,
                    hovertemplate='%{x|%Y-%m-%d}<br>순 충전: %{y}<extra></extra>'
                ))
                fig.add_hline(y=0, line_color="gray", line_width=1)
                fig.update_yaxes(title_text="Net Battery (충전 - 소모)")
                fig.update_layout(height=300, margin=dict(t=30), title="Body Battery (순 충전량)")
                st.plotly_chart(fig, width="stretch")

        # 4. Training Readiness (게이지 + 추세)
        st.header("4. Training Readiness")
        st.caption("훈련 준비도입니다. 🟢 50 이상 = 운동하기 좋은 날 | 🟠 30-49 = 가벼운 운동만 | 🔴 30 미만 = 휴식 권장")
        tr = hdf[hdf['training_readiness'].notna()].copy()
        if not tr.empty:
            col_gauge, col_trend = st.columns([1, 2])

            with col_gauge:
                latest_tr = tr.iloc[-1]['training_readiness']
                latest_level = tr.iloc[-1].get('training_readiness_level', '')
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=latest_tr,
                    title=dict(text=f"오늘 ({latest_level})"),
                    gauge=dict(
                        axis=dict(range=[0, 100]),
                        bar=dict(color='#636EFA'),
                        steps=[
                            dict(range=[0, 30], color='#FFCDD2'),
                            dict(range=[30, 50], color='#FFE0B2'),
                            dict(range=[50, 100], color='#C8E6C9'),
                        ],
                        threshold=dict(line=dict(color='red', width=2), thickness=0.75, value=latest_tr)
                    )
                ))
                fig.update_layout(height=250, margin=dict(t=50, b=10))
                st.plotly_chart(fig, width="stretch")

            with col_trend:
                colors = ['#00CC96' if v >= 50 else '#FFA15A' if v >= 30 else '#EF553B' for v in tr['training_readiness']]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=tr['date'], y=tr['training_readiness'], mode='lines+markers',
                    marker=dict(size=6, color=colors), line=dict(width=1, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y} (%{customdata})<extra></extra>',
                    customdata=tr['training_readiness_level']
                ))
                fig.add_hline(y=50, line_dash="dash", line_color="green", annotation_text="Good (50)")
                fig.add_hline(y=30, line_dash="dash", line_color="orange", annotation_text="Low (30)")
                fig.update_yaxes(range=[0, 100], title_text="Score")
                fig.update_layout(height=250, margin=dict(t=20))
                st.plotly_chart(fig, width="stretch")

        # 5. 체중/체지방 추이
        wt = hdf[hdf['weight_kg'].notna()].copy()
        if not wt.empty:
            st.header("5. Weight & Body Fat")
            st.caption("체중과 체지방률 추이입니다. 체중 변화보다 체지방률 변화가 체성분 개선 여부를 더 정확히 보여줍니다.")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=wt['date'], y=wt['weight_kg'], mode='lines+markers',
                name='Weight (kg)', marker=dict(size=5, color='#636EFA'), line=dict(width=2),
                hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f} kg<extra></extra>'
            ))
            bf = wt[wt['body_fat_pct'].notna()]
            if not bf.empty:
                fig.add_trace(go.Scatter(
                    x=bf['date'], y=bf['body_fat_pct'], mode='lines+markers',
                    name='Body Fat (%)', marker=dict(size=5, color='#FFA15A'), line=dict(width=2),
                    yaxis='y2',
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f}%<extra></extra>'
                ))
            fig.update_layout(
                height=350, margin=dict(t=20),
                yaxis=dict(title="Weight (kg)"),
                yaxis2=dict(title="Body Fat (%)", overlaying='y', side='right'),
                legend=dict(orientation="h", yanchor="top", y=-0.15)
            )
            st.plotly_chart(fig, width="stretch")

        # 6. Race Predictions 추이
        rp = hdf.copy()
        has_race = False
        for col in ['race_pred_5k', 'race_pred_10k', 'race_pred_half', 'race_pred_full']:
            if col in rp.columns and rp[col].notna().any():
                has_race = True
                break
        if has_race:
            st.header("6. Race Predictions")
            st.caption("가민이 추정한 레이스 예상 기록입니다. 숫자가 낮아질수록 체력이 향상되고 있는 것입니다.")
            fig = go.Figure()
            race_configs = [
                ('race_pred_5k', '5K', '#636EFA'),
                ('race_pred_10k', '10K', '#EF553B'),
                ('race_pred_half', 'Half', '#00CC96'),
                ('race_pred_full', 'Full', '#FFA15A'),
            ]
            for col, name, color in race_configs:
                if col in rp.columns:
                    rd = rp[rp[col].notna()].copy()
                    if not rd.empty:
                        # "HH:MM:SS" 또는 초 단위를 분으로 변환
                        def to_minutes(v):
                            try:
                                if isinstance(v, (int, float)):
                                    return float(v) / 60
                                parts = str(v).split(':')
                                if len(parts) == 3:
                                    return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60
                                elif len(parts) == 2:
                                    return int(parts[0]) + int(parts[1]) / 60
                            except:
                                return None
                            return None
                        rd['minutes'] = rd[col].apply(to_minutes)
                        rd = rd[rd['minutes'].notna()]
                        if not rd.empty:
                            # hover에 원래 시간 표시
                            fig.add_trace(go.Scatter(
                                x=rd['date'], y=rd['minutes'], mode='lines+markers',
                                name=name, marker=dict(size=5, color=color), line=dict(width=2),
                                hovertemplate='%{x|%Y-%m-%d}<br>%{customdata}<extra></extra>',
                                customdata=rd[col]
                            ))
            fig.update_yaxes(title_text="Time (min)", autorange="reversed")
            fig.update_layout(height=400, margin=dict(t=20),
                              legend=dict(orientation="h", yanchor="top", y=-0.15))
            st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════
# TAB 4: AI Coach
# ═══════════════════════════════════════════════════════════
with tab_ai:
    ai_conn = get_connection()
    try:
        ai_tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_analysis'", ai_conn)
        if ai_tables.empty:
            st.warning("AI 분석 데이터가 없습니다. `python scripts/ai_analyzer.py`를 실행하세요.")
        else:
            dates = pd.read_sql_query(
                "SELECT DISTINCT date FROM ai_analysis ORDER BY date DESC", ai_conn)

            if dates.empty:
                st.warning("AI 분석 데이터가 없습니다.")
            else:
                st.sidebar.header("🤖 AI Coach Filters")
                selected_date = st.sidebar.selectbox(
                    "분석 날짜 선택", dates['date'].tolist(), index=0, key="ai_date")

                # 비교 날짜 선택
                compare_dates = ["비교 안 함"] + [d for d in dates['date'].tolist() if d != selected_date]
                compare_date = st.sidebar.selectbox(
                    "비교할 날짜 (선택)", compare_dates, index=0, key="ai_compare")

                compare_mode = compare_date != "비교 안 함"

                if compare_mode:
                    st.header(f"🤖 AI Coach 비교 ({selected_date} vs {compare_date})")
                    st.caption("두 날짜의 AI 분석을 나란히 비교합니다.")
                else:
                    st.header(f"🤖 AI Coach Report ({selected_date})")
                    st.caption("Gemini AI가 가민 데이터를 기반으로 분석한 코칭 리포트입니다.")

                ai_tab1, ai_tab2, ai_tab3 = st.tabs(["📅 일간 분석", "📊 주간 분석", "📈 월간 분석"])

                labels = {"daily": "일간", "weekly": "주간", "monthly": "월간"}

                for tab, atype in [(ai_tab1, "daily"), (ai_tab2, "weekly"), (ai_tab3, "monthly")]:
                    with tab:
                        if compare_mode:
                            col_left, col_right = st.columns(2)
                            with col_left:
                                st.subheader(f"📌 {selected_date}")
                                row = pd.read_sql_query(
                                    "SELECT content, created_at FROM ai_analysis WHERE date = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1",
                                    ai_conn, params=[selected_date, atype])
                                if not row.empty:
                                    st.markdown(row.iloc[0]['content'])
                                    st.caption(f"🕐 {row.iloc[0]['created_at']}")
                                else:
                                    st.info(f"{labels[atype]} 분석 없음")
                            with col_right:
                                st.subheader(f"📌 {compare_date}")
                                row2 = pd.read_sql_query(
                                    "SELECT content, created_at FROM ai_analysis WHERE date = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1",
                                    ai_conn, params=[compare_date, atype])
                                if not row2.empty:
                                    st.markdown(row2.iloc[0]['content'])
                                    st.caption(f"🕐 {row2.iloc[0]['created_at']}")
                                else:
                                    st.info(f"{labels[atype]} 분석 없음")
                        else:
                            row = pd.read_sql_query(
                                "SELECT content, created_at FROM ai_analysis WHERE date = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1",
                                ai_conn, params=[selected_date, atype])
                            if not row.empty:
                                st.markdown(row.iloc[0]['content'])
                                st.divider()
                                st.caption(f"🕐 분석 시간: {row.iloc[0]['created_at']}")
                            else:
                                st.info(f"{labels[atype]} 분석 데이터가 없습니다.")
    except Exception as e:
        st.warning(f"AI 분석 로딩 실패: {e}")
