import streamlit as st
import pandas as pd
import pydeck as pdk

df = pd.read_csv("master_merged_data.csv")
df = df.fillna(0) #drops all the NaN datapoints and replaces them with a 0

#convert date column
df["date"] = pd.to_datetime(df["date"]).dt.date

#renaming columns bc it's easier
df = df.rename(columns={
    'latitude': 'lat',
    'longitude': 'lng',
})

#making a sidebar for date and layer control
st.sidebar.title("Filters")

### WORKING ON CHOOSING THE DATE ###

#finds earliest and latest date for the bounds
min_date = df["date"].min()
max_date = df["date"].max()

#need to initalize a session state for date syncing
if "selected_date" not in st.session_state:
    st.session_state.selected_date = min_date

#helper to normalize date types
def to_date(x):
    if hasattr(x, "date"):
        return x.date()
    return x

#callback functions
def manual_changed():
    st.session_state.selected_date = to_date(st.session_state.manual_date)
    st.session_state.slider_date = st.session_state.selected_date  # sync slider

def slider_changed():
    st.session_state.selected_date = to_date(st.session_state.slider_date)
    st.session_state.manual_date = st.session_state.selected_date  # sync input

#make date input box
st.sidebar.date_input(
    "Enter Date (must be in the year 2025):",
    value=st.session_state.selected_date,
    min_value=min_date,
    max_value=max_date,
    key="manual_date",
    on_change=manual_changed
)

#make date slider
st.sidebar.slider(
    "Select Date:",
    min_value=min_date,
    max_value=max_date,
    value=st.session_state.selected_date,
    format="YYYY-MM-DD",
    key="slider_date",
    on_change=slider_changed
)

selected_date = st.session_state.selected_date

### END DATE SELECTION PART ###

#select your layer
selected_layer = st.sidebar.selectbox(
    "Select Layer:",
    ["pm25", "fire_frp_sum", "wind_speed"]
)

#filters for the day and makes sure it's a valid date
df_day = df[df["date"] == selected_date]
if df_day.empty:
    st.warning("No data for this day")
    st.stop()
df_day = df_day.drop(columns=["date"])

#ok time for the heatmap
#layer = pdk.Layer(
#    "HeatmapLayer",
#    data = df_day,
#    get_position = ["lng", "lat"],
#    get_weight = selected_layer,
#    radius_pixels = 50,
#)

#let's try a scatterplot map
#making sure the sizing of dot is dynamic
df_day["radius"] = df_day[selected_layer] * 2000
#figuring out color scale
df_day["color_value"] = (df_day[selected_layer] * 10).clip(0, 255)
df_day["color"] = df_day["color_value"].apply(lambda v: [v, 50, 255 - v, 200])
#creating the layer
layer = pdk.Layer(
    "ScatterplotLayer",
    data = df_day,
    get_position = ["lng", "lat"],
    get_radius="radius",
    get_fill_color = "color",
    pickable = True,
)

# set view to cali!!!
view_state = pdk.ViewState(
    latitude=df_day['lat'].mean(),
    longitude=df_day['lng'].mean(),
    zoom=6,
    pitch=45
)

#adding a title
st.title("Los Angeles Air Quality Heatmap")

#showing the layers!
r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": f"{selected_layer}: {{{selected_layer}}}"},
)

st.pydeck_chart(r)