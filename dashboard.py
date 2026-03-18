import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path
from datetime import timedelta

DB_PATH = Path(__file__).parent / "analysis.db"

st.set_page_config(page_title="Garmin Analytics", layout="wide")
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


@st.cache_data(ttl=300)
def load_run_data():
    df = safe_load("SELECT * FROM run_analysis ORDER BY activity_date")
    if 'activity_date' in df.columns:
        df['activity_date'] = pd.to_datetime(df['activity_date'])
        df['week'] = df['activity_date'].dt.isocalendar().year.astype(str) + '-W' + df['activity_date'].dt.isocalendar().week.astype(str).str.zfill(2)
    return df


@st.cache_data(ttl=300)
def load_cycling_data():
    df = safe_load("SELECT * FROM cycling_analysis ORDER BY activity_date")
    if 'activity_date' in df.columns:
        df['activity_date'] = pd.to_datetime(df['activity_date'])
        df['week'] = df['activity_date'].dt.isocalendar().year.astype(str) + '-W' + df['activity_date'].dt.isocalendar().week.astype(str).str.zfill(2)
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
tab_overview, tab_run, tab_bike, tab_health = st.tabs([
    "📊 Overview", "🏃 Running", "🚴 Cycling", "❤️ Health"
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
        # Overview 날짜 필터
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
                value=(max(ov_date_min, ov_date_max - timedelta(days=90)), ov_date_max),
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
            st.header("Today's Status")
            latest = hdf_all.iloc[-1]
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1:
                v = latest.get('training_readiness')
                lv = latest.get('training_readiness_level', '')
                st.metric("Training Readiness", f"{int(v)} ({lv})" if pd.notna(v) else "N/A")
            with c2:
                v = latest.get('sleep_score')
                st.metric("Sleep Score", f"{int(v)}" if pd.notna(v) else "N/A")
            with c3:
                v = latest.get('resting_hr')
                st.metric("Resting HR", f"{int(v)} bpm" if pd.notna(v) else "N/A")
            with c4:
                v = latest.get('body_battery_max')
                st.metric("Body Battery", f"{int(v)}" if pd.notna(v) else "N/A")
            with c5:
                v = latest.get('avg_stress')
                st.metric("Avg Stress", f"{int(v)}" if pd.notna(v) else "N/A")
            with c6:
                v = latest.get('steps')
                st.metric("Steps", f"{int(v):,}" if pd.notna(v) else "N/A")

            st.divider()

        # ─── 주간 운동 볼륨 (러닝 + 사이클링) ───────────
        st.header("Weekly Training Volume")
        weekly_data = []
        if not run_df.empty:
            rw = run_df.groupby('week').agg(run_km=('total_distance_km', 'sum')).reset_index()
            weekly_data.append(rw.set_index('week'))
        if not cyc_df.empty:
            cw = cyc_df.groupby('week').agg(bike_km=('total_distance_km', 'sum')).reset_index()
            weekly_data.append(cw.set_index('week'))

        if weekly_data:
            combined = pd.concat(weekly_data, axis=1).fillna(0).reset_index()
            combined.columns.name = None
            if 'run_km' not in combined.columns:
                combined['run_km'] = 0
            if 'bike_km' not in combined.columns:
                combined['bike_km'] = 0
            combined['run_km'] = combined['run_km'].round(1)
            combined['bike_km'] = combined['bike_km'].round(1)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=combined['week'], y=combined['run_km'], name='Running', marker_color='#EF553B'))
            fig.add_trace(go.Bar(x=combined['week'], y=combined['bike_km'], name='Cycling', marker_color='#636EFA'))
            fig.update_layout(barmode='stack', height=400, margin=dict(t=20), yaxis_title="Distance (km)",
                              legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
            st.plotly_chart(fig, use_container_width=True)

        # ─── Recovery vs Training ────────────────────────
        if not hdf.empty:
            st.header("Recovery & Training Trend")
            col_rec, col_tr = st.columns(2)

            with col_rec:
                rec_df = hdf[['date', 'sleep_score', 'hrv_ms']].dropna(subset=['sleep_score'])
                if not rec_df.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=rec_df['date'], y=rec_df['sleep_score'], mode='lines+markers',
                        name='Sleep Score', marker=dict(size=4, color='#636EFA'), line=dict(width=1)
                    ))
                    hrv_valid = rec_df[rec_df['hrv_ms'].notna()]
                    if not hrv_valid.empty:
                        fig.add_trace(go.Scatter(
                            x=hrv_valid['date'], y=hrv_valid['hrv_ms'], mode='lines+markers',
                            name='HRV (ms)', marker=dict(size=4, color='#00CC96'), line=dict(width=1),
                            yaxis='y2'
                        ))
                    fig.update_layout(
                        height=350, margin=dict(t=30), title="Recovery Indicators",
                        yaxis=dict(title="Sleep Score", range=[0, 100]),
                        yaxis2=dict(title="HRV (ms)", overlaying='y', side='right'),
                        legend=dict(orientation="h", yanchor="top", y=-0.15)
                    )
                    st.plotly_chart(fig, use_container_width=True)

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
                    st.plotly_chart(fig, use_container_width=True)

        # ─── VO2 Max 추이 ───────────────────────────────
        if not hdf.empty:
            vo2_df = hdf[(hdf['vo2_max_running'].notna()) | (hdf['vo2_max_cycling'].notna())].copy()
            if not vo2_df.empty:
                st.header("VO2 Max Trend")
                fig = go.Figure()
                run_v = vo2_df[vo2_df['vo2_max_running'].notna()]
                if not run_v.empty:
                    fig.add_trace(go.Scatter(
                        x=run_v['date'], y=run_v['vo2_max_running'], mode='markers+lines',
                        name='Running', marker=dict(size=6, color='#EF553B'), line=dict(width=1)
                    ))
                cyc_v = vo2_df[vo2_df['vo2_max_cycling'].notna()]
                if not cyc_v.empty:
                    fig.add_trace(go.Scatter(
                        x=cyc_v['date'], y=cyc_v['vo2_max_cycling'], mode='markers+lines',
                        name='Cycling', marker=dict(size=6, color='#636EFA'), line=dict(width=1)
                    ))
                fig.update_yaxes(title_text="VO2 Max")
                fig.update_layout(height=350, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15))
                st.plotly_chart(fig, use_container_width=True)

        # ─── 총 요약 (전체 기간) ─────────────────────────
        st.divider()
        st.caption("All-Time Summary")
        run_all = load_run_data()
        cyc_all = load_cycling_data()
        c1, c2, c3, c4, c5 = st.columns(5)
        run_km = run_all['total_distance_km'].sum() if not run_all.empty else 0
        bike_km = cyc_all['total_distance_km'].sum() if not cyc_all.empty else 0
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

            # 1. Zone2 Pace Trend
            st.header("1. Zone2 Pace Trend")
            st.caption("Zone2 비율 30% 이상. Lower = faster.")
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
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Zone2 pace data not available.")

            # 2. HR Drift
            st.header("2. HR Drift")
            st.caption("Below 5% = good. Above 7% = needs attention.")
            if not hr.empty:
                colors = ['#00CC96' if v <= 5 else '#FFA15A' if v <= 7 else '#EF553B' for v in hr['hr_drift_percent']]
                fig = go.Figure(go.Bar(x=hr['activity_date'], y=hr['hr_drift_percent'], marker_color=colors,
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>'))
                fig.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5%")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True)

            # 3. Weekly Distance
            st.header("3. Weekly Distance")
            wd = df[df['total_distance_km'].notna()].copy()
            if not wd.empty:
                weekly = wd.groupby('week').agg(total_km=('total_distance_km', 'sum'), runs=('total_distance_km', 'count')).reset_index()
                weekly['total_km'] = weekly['total_km'].round(1)
                fig = px.bar(weekly, x='week', y='total_km', hover_data={'runs': True})
                fig.update_traces(marker_color='#EF553B')
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True)

            # 4. Pace Stability
            st.header("4. Pace Stability (8km+)")
            st.caption("CV < 7.5% = stable pacing.")
            ps = df[df['pace_stability_cv'].notna()].copy()
            if not ps.empty:
                fig = go.Figure(go.Scatter(x=ps['activity_date'], y=ps['pace_stability_cv'], mode='markers+lines',
                    marker=dict(size=8, color='#AB63FA'), line=dict(color='#AB63FA', width=1),
                    hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                    customdata=ps['total_distance_km']))
                fig.add_hline(y=7.5, line_dash="dash", line_color="green", annotation_text="7.5%")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True)


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

            # 1. Zone2 Speed Trend
            st.header("1. Zone2 Speed Trend")
            st.caption("Zone2 비율 20% 이상. Higher = better aerobic fitness.")
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
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Zone2 speed data not available.")

            # 2. HR Drift
            st.header("2. HR Drift")
            st.caption("Below 5% = good. Above 7% = dehydration or fatigue risk.")
            if not hr_c.empty:
                colors = ['#00CC96' if v <= 5 else '#FFA15A' if v <= 7 else '#EF553B' for v in hr_c['hr_drift_percent']]
                fig = go.Figure(go.Bar(x=hr_c['activity_date'], y=hr_c['hr_drift_percent'], marker_color=colors,
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>'))
                fig.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5%")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True)

            # 3. Weekly Distance
            st.header("3. Weekly Distance")
            cyc_weekly = cdf.groupby('week').agg(total_km=('total_distance_km', 'sum'), rides=('total_distance_km', 'count')).reset_index()
            cyc_weekly['total_km'] = cyc_weekly['total_km'].round(1)
            fig = px.bar(cyc_weekly, x='week', y='total_km', hover_data={'rides': True})
            fig.update_traces(marker_color='#636EFA')
            fig.update_layout(height=400, margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)

            # 4. Avg Speed Trend
            st.header("4. Avg Speed Trend")
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
                st.plotly_chart(fig, use_container_width=True)

            # 5. Power Trend
            if 'avg_power' in cdf.columns and cdf['avg_power'].notna().any():
                st.header("5. Power Trend")
                pwr = cdf[cdf['avg_power'].notna()].copy()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=pwr['activity_date'], y=pwr['avg_power'], mode='markers',
                    name='Avg Power', marker=dict(size=6, color='#FFA15A'),
                    hovertemplate='%{x|%Y-%m-%d}<br>Avg: %{y:.0f}W<extra></extra>'))
                if 'normalized_power' in pwr.columns:
                    np_df = pwr[pwr['normalized_power'].notna()]
                    if not np_df.empty:
                        fig.add_trace(go.Scatter(x=np_df['activity_date'], y=np_df['normalized_power'],
                            mode='markers+lines', name='Normalized Power',
                            marker=dict(size=6, color='#EF553B'), line=dict(width=1),
                            hovertemplate='%{x|%Y-%m-%d}<br>NP: %{y:.0f}W<extra></extra>'))
                fig.update_yaxes(title_text="Power (W)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, use_container_width=True)

                # 6. Power Zone Distribution
                st.header("6. Power Zone Distribution")
                st.caption("FTP 기준 파워 존 분포. 최근 라이드와 전체 평균 비교.")
                # Power zone은 FIT 파일에서 직접 계산해야 하므로,
                # 여기서는 avg_power 기반으로 라이드별 강도 분포를 표시
                pwr_rides = cdf[cdf['avg_power'].notna()].copy()
                if not pwr_rides.empty:
                    # 간이 강도 분류 (avg_power 기준)
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

                    fig = px.bar(zone_counts, x='zone', y='count', color='zone',
                                 color_discrete_map=zone_colors,
                                 labels={'count': 'Rides', 'zone': 'Power Zone'})
                    fig.update_layout(height=400, margin=dict(t=20), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

            # 7. Speed Stability (20km+)
            if 'speed_stability_cv' in cdf.columns:
                ss = cdf[cdf['speed_stability_cv'].notna()].copy()
                if not ss.empty:
                    st.header("7. Speed Stability (20km+)")
                    st.caption("5km 구간별 속도 변동계수. Lower = more consistent.")
                    fig = go.Figure(go.Scatter(x=ss['activity_date'], y=ss['speed_stability_cv'],
                        mode='markers+lines', marker=dict(size=8, color='#AB63FA'), line=dict(width=1),
                        hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                        customdata=ss['total_distance_km']))
                    fig.add_hline(y=10, line_dash="dash", line_color="green", annotation_text="10%")
                    fig.update_layout(height=400, margin=dict(t=20))
                    st.plotly_chart(fig, use_container_width=True)


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
        h_range = st.sidebar.date_input("Health date range", value=(max(h_min, h_max - timedelta(days=90)), h_max),
                                         min_value=h_min, max_value=h_max, key="health_date")
        if len(h_range) == 2:
            hdf = hdf[(hdf['date'].dt.date >= h_range[0]) & (hdf['date'].dt.date <= h_range[1])]

        # 1. Sleep
        st.header("1. Sleep Score")
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
            st.plotly_chart(fig, use_container_width=True)

        # 2. Resting HR + HRV
        st.header("2. Resting HR & HRV")
        col1, col2 = st.columns(2)
        with col1:
            rhr = hdf[hdf['resting_hr'].notna()]
            if not rhr.empty:
                fig = go.Figure(go.Scatter(x=rhr['date'], y=rhr['resting_hr'], mode='markers+lines',
                    marker=dict(size=4, color='#EF553B'), line=dict(width=1)))
                fig.update_yaxes(title_text="bpm")
                fig.update_layout(height=300, margin=dict(t=30), title="Resting HR")
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            hrv = hdf[hdf['hrv_ms'].notna()]
            if not hrv.empty:
                fig = go.Figure(go.Scatter(x=hrv['date'], y=hrv['hrv_ms'], mode='markers+lines',
                    marker=dict(size=4, color='#00CC96'), line=dict(width=1)))
                fig.update_yaxes(title_text="ms")
                fig.update_layout(height=300, margin=dict(t=30), title="HRV")
                st.plotly_chart(fig, use_container_width=True)

        # 3. Stress + Body Battery
        st.header("3. Stress & Body Battery")
        col1, col2 = st.columns(2)
        with col1:
            stress = hdf[hdf['avg_stress'].notna()]
            if not stress.empty:
                fig = go.Figure(go.Scatter(x=stress['date'], y=stress['avg_stress'], mode='markers+lines',
                    marker=dict(size=4, color='#FFA15A'), line=dict(width=1)))
                fig.update_yaxes(range=[0, 100], title_text="Stress")
                fig.update_layout(height=300, margin=dict(t=30), title="Avg Stress")
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            bb = hdf[hdf['body_battery_max'].notna()]
            if not bb.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=bb['date'], y=bb['body_battery_max'], name='Charged', marker_color='#00CC96'))
                fig.add_trace(go.Bar(x=bb['date'], y=bb['body_battery_drain'], name='Drained', marker_color='#EF553B'))
                fig.update_layout(height=300, margin=dict(t=30), title="Body Battery", barmode='group')
                st.plotly_chart(fig, use_container_width=True)

        # 4. Training Readiness
        st.header("4. Training Readiness")
        tr = hdf[hdf['training_readiness'].notna()]
        if not tr.empty:
            colors = ['#00CC96' if v >= 50 else '#FFA15A' if v >= 30 else '#EF553B' for v in tr['training_readiness']]
            fig = go.Figure(go.Bar(x=tr['date'], y=tr['training_readiness'], marker_color=colors,
                hovertemplate='%{x|%Y-%m-%d}<br>%{y} (%{customdata})<extra></extra>',
                customdata=tr['training_readiness_level']))
            fig.update_yaxes(range=[0, 100], title_text="Score")
            fig.update_layout(height=350, margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)
