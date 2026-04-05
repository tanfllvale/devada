import streamlit as st
import pandas as pd
import pydeck as pdk
from datetime import timedelta
from datetime import date

#loading everything
#allows streamlit to not have to re-read the file over and over
@st.cache_data
def load_data():
    df = pd.read_csv("master_merged_data.csv")
    df = df.fillna(0)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    # renames coords to be shorter
    df = df.rename(columns={'latitude': 'lat', 'longitude': 'lng', 'fire_frp_sum':'fire_intensity', 'pm25': 'pm2.5'})
    return df

df = load_data()

# create predicted db
df2 = df.copy()

# takes current date and adds a year to it
df2["date"] = df2["date"].apply(lambda x: x + timedelta(days=365))

# load and merge forecasted values
sarimax_df = pd.read_csv("sarimax_forecast.csv")
sarimax_df["date"] = pd.to_datetime(sarimax_df["date"]).dt.date

#change col name
if "forecasted_fire_frp" in sarimax_df.columns:
    sarimax_df.rename(columns={"forecasted_fire_frp": "forecasted_fire_intensity"}, inplace=True)

df2 = pd.merge(df2, sarimax_df, on="date", how="left")
df2["forecasted_fire_intensity"] = df2["forecasted_fire_intensity"].interpolate(method="linear").bfill().ffill()

#sidebar 
st.sidebar.markdown("### Filters")

#radio toggle
mode = st.sidebar.radio("Data View:", ["Current Values", "Predicted Values"], key="main_mode_toggle")
st.sidebar.markdown("---")

#dropdown options
if mode == "Current Values":
    active_df = df
    metric_options = ["pm2.5", "fire_intensity", "wind_speed"]
else:
    active_df = df2
    metric_options = ["forecasted_fire_intensity"]

#date bounds for slider and values below map
min_date = active_df["date"].min()
max_date = active_df["date"].max()

#set slider to min date when nothing is selected
if "selected_date" not in st.session_state:
    st.session_state.selected_date = min_date

#input box in bounds
if st.session_state.selected_date < min_date:
    st.session_state.selected_date = min_date
elif st.session_state.selected_date > max_date:
    st.session_state.selected_date = max_date

#link slider and date in box
def slider_changed():
    st.session_state.selected_date = st.session_state.slider_date

#slider frontend
st.sidebar.slider(
    "Select Date:",
    min_value=min_date,
    max_value=max_date,
    value=st.session_state.selected_date,
    format="YYYY-MM-DD",
    key="slider_date",
    on_change=slider_changed
)

# makes empty contianer
placeholder = st.sidebar.empty()

with placeholder:
    selected_layer = st.selectbox(
        "Select Metric:", 
        options=metric_options, 
        key=f"widget_{mode}" # key
    )

selected_date = st.session_state.selected_date

# variable for df data day 
df_day = active_df[active_df["date"] == selected_date].copy()

if df_day.empty:
    st.warning(f"No data for {selected_date}")
    st.stop()

# get min/max
max_val = active_df[selected_layer].max()
min_val = active_df[selected_layer].min()

#radius bounds for dot
MAX_RADIUS = 20000  
MIN_RADIUS = 2000  

#computing mean
if max_val <= min_val:
    df_day["normalized_intensity"] = 0.5 
else:
    df_day["normalized_intensity"] = (df_day[selected_layer] - min_val) / (max_val - min_val)

# apply scale
df_day["radius"] = (df_day["normalized_intensity"] * (MAX_RADIUS - MIN_RADIUS)) + MIN_RADIUS

#color logic
def get_clean_color(row):
    intensity = row["normalized_intensity"]
    val = int(intensity * 255)
    
    if mode == "Current Values":
        return [val, 50, 255 - val, 200]
    else:
        return [255, 100 + int(intensity * 100), 0, 210]

df_day["color"] = df_day.apply(get_clean_color, axis=1)

render_df = df_day[["lat", "lng", "radius", "color", selected_layer]].copy().reset_index(drop=True)

#makes map
st.title("Los Angeles Air Quality Dashboard")
st.subheader(f"Viewing: {mode}")

#center map
center_lat = float(render_df['lat'].mean())
center_lng = float(render_df['lng'].mean())

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lng,
    zoom=8,
    pitch=45
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=render_df,
    get_position=["lng", "lat"],
    get_radius="radius",
    get_fill_color="color",
    pickable=True,
    opacity=0.8
)

#set map aesthetics
r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="dark", 
    tooltip={"text": f"{selected_layer}: {{{selected_layer}}}"},
)

st.pydeck_chart(r)

#metrics under map
st.markdown("Data Summary")
m1, m2, m3, m4 = st.columns(4)

day_avg = render_df[selected_layer].mean()
global_avg = active_df[selected_layer].mean()

with m1:
    st.metric("Day Average", f"{day_avg:.2f}", 
              delta=f"{day_avg - global_avg:.2f} vs Avg", delta_color="inverse")
with m2:
    st.metric("Global Average", f"{global_avg:.2f}")
with m3:
    st.metric("Record Max", f"{active_df[selected_layer].max():.2f}")
with m4:
    st.metric("Record Min", f"{active_df[selected_layer].min():.2f}")

   