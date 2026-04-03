import streamlit as st
import pandas as pd
import pydeck as pdk
from datetime import timedelta
from datetime import date

# pt 1: loading everything
# allows streamlit to not have to re-read the file over and over
@st.cache_data
def load_data():
    df = pd.read_csv("master_merged_data.csv")
    df = df.fillna(0)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    # renames coords to be shorter
    df = df.rename(columns={'latitude': 'lat', 'longitude': 'lng'})
    return df

df = load_data()

# create predicted db
df2 = pd.read_csv("sarimax_forecast.csv")
df2["date"] = pd.to_datetime(df2["date"]).dt.date

# pt 2: sidebar
st.sidebar.markdown("Filters")

#makes radio toggle
mode = st.sidebar.radio("Data View:", ["Current Values", "Predicted Values"])
st.sidebar.markdown("---")

# determines dataset to use
if mode == "Current Values":
    active_df = df
    metric_options = ["pm25", "fire_frp_sum", "wind_speed"]
else:
    active_df = df2
    metric_options = ["fire_frp_sum"]

min_date = active_df["date"].min()
max_date = active_df["date"].max()

# --- pt 2: sidebar & mode logic ---
# --- pt 2: sidebar & mode logic ---
st.sidebar.markdown("### Filters")

# 1. The Radio Toggle
mode = st.sidebar.radio("Data View:", ["Current Values", "Predicted Values"], key="main_mode_toggle")
st.sidebar.markdown("---")

# 2. Assign the specific list of columns based on the choice
if mode == "Current Values":
    active_df = df
    metric_options = ["fire_frp_sum"]
else:
    active_df = df2
    metric_options = ["pm25", "fire_frp_sum", "wind_speed"]

# 3. Get date bounds
min_date = active_df["date"].min()
max_date = active_df["date"].max()

# --- pt 3: slider & metric selection ---

# Initialize session state for date
if "selected_date" not in st.session_state:
    st.session_state.selected_date = min_date

# Force the date into the valid range of the active dataframe
if st.session_state.selected_date < min_date:
    st.session_state.selected_date = min_date
elif st.session_state.selected_date > max_date:
    st.session_state.selected_date = max_date

# Callback functions
def manual_changed():
    st.session_state.selected_date = st.session_state.manual_date

def slider_changed():
    st.session_state.selected_date = st.session_state.slider_date

# Date Input
st.sidebar.date_input(
    "Enter Date:",
    value=st.session_state.selected_date,
    min_value=min_date,
    max_value=max_date,
    key="manual_date",
    on_change=manual_changed
)

# Slider
st.sidebar.slider(
    "Select Date:",
    min_value=min_date,
    max_value=max_date,
    value=st.session_state.selected_date,
    format="YYYY-MM-DD",
    key="slider_date",
    on_change=slider_changed
)

# --- THE FIX: DYNAMIC SELECTBOX ---
# We use a placeholder container to force a redraw
placeholder = st.sidebar.empty()

with placeholder:
    # We use the 'options' variable we defined in the IF statement above
    selected_layer = st.selectbox(
        "Select Metric:", 
        options=metric_options, 
        key=f"widget_{mode}" # This key MUST change when mode changes
    )

selected_date = st.session_state.selected_date

# Radio toggle to switch between datasets

# --- 4. FILTERING & DATA CLEANING ---
# --- 4. FILTERING & DYNAMIC SCALING ---
df_day = active_df[active_df["date"] == selected_date].copy()

if df_day.empty:
    st.warning(f"No data for {selected_date}")
    st.stop()

# 1. STANDARDIZATION LOGIC
max_val = active_df[selected_layer].max()
min_val = active_df[selected_layer].min()

# --- TWEAK THESE NUMBERS TO YOUR LIKING ---
MAX_RADIUS = 20000  # Increased this for a "bigger" look
MIN_RADIUS = 2000   # The smallest a dot will ever be
# ------------------------------------------

if max_val <= min_val:
    df_day["normalized_intensity"] = 0.5 # Default middle-ground
else:
    df_day["normalized_intensity"] = (df_day[selected_layer] - min_val) / (max_val - min_val)

# Apply the bigger scale
df_day["radius"] = (df_day["normalized_intensity"] * (MAX_RADIUS - MIN_RADIUS)) + MIN_RADIUS

# 2. COLOR LOGIC (Standardized)
def get_clean_color(row):
    intensity = row["normalized_intensity"]
    val = int(intensity * 255)
    
    if mode == "Current Values":
        return [val, 50, 255 - val, 200]
    else:
        # Bright neon orange for predicted values
        return [255, 100 + int(intensity * 100), 0, 210]

df_day["color"] = df_day.apply(get_clean_color, axis=1)

render_df = df_day[["lat", "lng", "radius", "color", selected_layer]].copy().reset_index(drop=True)

# --- 5. MAP RENDERING ---
st.title("Los Angeles Air Quality Dashboard")
st.subheader(f"Viewing: {mode}")

# Centering the map
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

# "dark" or "light" are standard styles that don't usually require a Mapbox token
r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="dark", 
    tooltip={"text": f"{selected_layer}: {{{selected_layer}}}"},
)

st.pydeck_chart(r)

# --- 6. METRICS (Under the Map) ---
st.markdown("Data Summary")
m1, m2, m3, m4 = st.columns(4)

day_avg = render_df[selected_layer].mean()
global_avg = active_df[selected_layer].mean()

with m1:
    # Inverse color: Higher values (pollution) show as a "bad" red delta
    st.metric("Day Average", f"{day_avg:.2f}", 
              delta=f"{day_avg - global_avg:.2f} vs Avg", delta_color="inverse")
with m2:
    st.metric("Global Average", f"{global_avg:.2f}")
with m3:
    st.metric("Record Max", f"{active_df[selected_layer].max():.2f}")
with m4:
    st.metric("Record Min", f"{active_df[selected_layer].min():.2f}")

    #run everything on colab to get 2 csv file
    #m