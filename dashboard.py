import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "analysis.db"

st.set_page_config(page_title="Garmin Analytics", layout="wide")
st.title("🏃 Garmin Analytics Dashboard")


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


# ─── 탭 구성 (2개) ────────────────────────────────────────
tab_run, tab_bike = st.tabs(["🏃 Running", "🚴 Cycling"])


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
        date_range = st.sidebar.date_input("Run date range", value=(date_min, date_max),
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
            with c1:
                st.metric("Total Runs", len(df))
            with c2:
                st.metric("Total Distance", f"{df['total_distance_km'].sum():.0f} km")
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
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=z2['activity_date'], y=z2['pace_minutes'], mode='markers',
                    name='Pace', marker=dict(size=8, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{customdata}<extra></extra>',
                    customdata=z2['zone2_avg_pace_min_km']
                ))
                fig1.add_trace(go.Scatter(
                    x=z2['activity_date'], y=z2['rolling_avg'], mode='lines',
                    name='5-run avg', line=dict(color='#EF553B', width=2)
                ))
                pace_min, pace_max = z2['pace_minutes'].min(), z2['pace_minutes'].max()
                pad = (pace_max - pace_min) * 0.3 if pace_max > pace_min else 0.5
                fig1.update_yaxes(title_text="Pace (min/km)", range=[pace_max + pad, pace_min - pad])
                fig1.update_layout(height=400, margin=dict(t=20),
                                   legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Zone2 pace data not available.")

            # 2. HR Drift
            st.header("2. HR Drift")
            st.caption("Below 5% = good. Above 7% = needs attention.")
            if not hr.empty:
                colors = ['#00CC96' if v <= 5 else '#FFA15A' if v <= 7 else '#EF553B' for v in hr['hr_drift_percent']]
                fig2 = go.Figure(go.Bar(
                    x=hr['activity_date'], y=hr['hr_drift_percent'], marker_color=colors,
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>'
                ))
                fig2.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5%")
                fig2.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("HR drift data not available.")

            # 3. Weekly Distance
            st.header("3. Weekly Distance")
            wd = df[df['total_distance_km'].notna()].copy()
            if not wd.empty:
                weekly = wd.groupby('week').agg(
                    total_km=('total_distance_km', 'sum'), runs=('total_distance_km', 'count')
                ).reset_index()
                weekly['total_km'] = weekly['total_km'].round(1)
                fig3 = px.bar(weekly, x='week', y='total_km', hover_data={'runs': True})
                fig3.update_traces(marker_color='#EF553B')
                fig3.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig3, use_container_width=True)

            # 4. Pace Stability
            st.header("4. Pace Stability (8km+)")
            st.caption("CV < 7.5% = stable pacing.")
            ps = df[df['pace_stability_cv'].notna()].copy()
            if not ps.empty:
                fig4 = go.Figure(go.Scatter(
                    x=ps['activity_date'], y=ps['pace_stability_cv'], mode='markers+lines',
                    marker=dict(size=8, color='#AB63FA'), line=dict(color='#AB63FA', width=1),
                    hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                    customdata=ps['total_distance_km']
                ))
                fig4.add_hline(y=7.5, line_dash="dash", line_color="green", annotation_text="7.5%")
                fig4.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("No long runs (8km+) with pace stability data.")


# ═══════════════════════════════════════════════════════════
# TAB 2: Cycling Analysis
# ═══════════════════════════════════════════════════════════
with tab_bike:
    cdf = load_cycling_data()
    if cdf.empty:
        st.warning("사이클링 분석 데이터가 없습니다. FIT 파일 동기화 후 분석을 실행하세요.")
    else:
        st.sidebar.header("🚴 Cycling Filters")
        c_date_min = cdf['activity_date'].min().date()
        c_date_max = cdf['activity_date'].max().date()
        c_date_range = st.sidebar.date_input("Bike date range", value=(c_date_min, c_date_max),
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
            with c1:
                st.metric("Total Rides", len(cdf))
            with c2:
                st.metric("Total Distance", f"{cdf['total_distance_km'].sum():.0f} km")
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
                fig.add_trace(go.Scatter(
                    x=z2c['activity_date'], y=z2c['zone2_avg_speed_kmh'], mode='markers',
                    name='Speed', marker=dict(size=8, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f} km/h<extra></extra>'
                ))
                fig.add_trace(go.Scatter(
                    x=z2c['activity_date'], y=z2c['rolling_avg'], mode='lines',
                    name='5-ride avg', line=dict(color='#EF553B', width=2)
                ))
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
                fig = go.Figure(go.Bar(
                    x=hr_c['activity_date'], y=hr_c['hr_drift_percent'], marker_color=colors,
                    hovertemplate='%{x|%Y-%m-%d}<br>Drift: %{y:.1f}%<extra></extra>'
                ))
                fig.add_hline(y=5, line_dash="dash", line_color="green", annotation_text="5%")
                fig.update_layout(height=400, margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("HR drift data not available.")

            # 3. Weekly Distance
            st.header("3. Weekly Distance")
            cyc_weekly = cdf.groupby('week').agg(
                total_km=('total_distance_km', 'sum'), rides=('total_distance_km', 'count')
            ).reset_index()
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
                fig.add_trace(go.Scatter(
                    x=spd['activity_date'], y=spd['avg_speed_kmh'], mode='markers',
                    name='Avg Speed', marker=dict(size=6, color='#636EFA'),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.1f} km/h<extra></extra>'
                ))
                fig.add_trace(go.Scatter(
                    x=spd['activity_date'], y=spd['rolling_avg'], mode='lines',
                    name='5-ride avg', line=dict(color='#EF553B', width=2)
                ))
                fig.update_yaxes(title_text="Speed (km/h)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, use_container_width=True)

            # 5. Power (있는 경우)
            if 'avg_power' in cdf.columns and cdf['avg_power'].notna().any():
                st.header("5. Power Trend")
                pwr = cdf[cdf['avg_power'].notna()].copy()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pwr['activity_date'], y=pwr['avg_power'], mode='markers',
                    name='Avg Power', marker=dict(size=6, color='#FFA15A'),
                    hovertemplate='%{x|%Y-%m-%d}<br>Avg: %{y:.0f}W<extra></extra>'
                ))
                if 'normalized_power' in pwr.columns:
                    np_df = pwr[pwr['normalized_power'].notna()]
                    if not np_df.empty:
                        fig.add_trace(go.Scatter(
                            x=np_df['activity_date'], y=np_df['normalized_power'], mode='markers+lines',
                            name='Normalized Power', marker=dict(size=6, color='#EF553B'), line=dict(width=1),
                            hovertemplate='%{x|%Y-%m-%d}<br>NP: %{y:.0f}W<extra></extra>'
                        ))
                fig.update_yaxes(title_text="Power (W)")
                fig.update_layout(height=400, margin=dict(t=20),
                                  legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
                st.plotly_chart(fig, use_container_width=True)

            # 6. Speed Stability (20km+)
            if 'speed_stability_cv' in cdf.columns:
                ss = cdf[cdf['speed_stability_cv'].notna()].copy()
                if not ss.empty:
                    st.header("6. Speed Stability (20km+)")
                    st.caption("5km 구간별 속도 변동계수. Lower = more consistent.")
                    fig = go.Figure(go.Scatter(
                        x=ss['activity_date'], y=ss['speed_stability_cv'], mode='markers+lines',
                        marker=dict(size=8, color='#AB63FA'), line=dict(color='#AB63FA', width=1),
                        hovertemplate='%{x|%Y-%m-%d}<br>CV: %{y:.1f}%<br>%{customdata:.1f}km<extra></extra>',
                        customdata=ss['total_distance_km']
                    ))
                    fig.add_hline(y=10, line_dash="dash", line_color="green", annotation_text="10%")
                    fig.update_layout(height=400, margin=dict(t=20))
                    st.plotly_chart(fig, use_container_width=True)

