"""
Milton Transit Desert Analysis
Spatial transit analysis for Milton, Ontario.
"""

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point
import numpy as np
import matplotlib.pyplot as plt

# --- load datasets ---
stops_df = pd.read_csv("data/stops.txt")
stop_times_df = pd.read_csv("data/stop_times.txt")

# --- previewing the data ---
print("\n--- stops data head ---")
print(stops_df.head())

print("\n--- stop times data head ---")
print(stop_times_df.head())

print("\n--- stops columns ---")
print(stops_df.columns.tolist())

print("\n--- stop times columns ---")
# turns out stop_times has 121k rows, way more than expected
print(stop_times_df.columns.tolist())

print("\n--- shape check ---")
print(f"Stops: {stops_df.shape[0]} rows, {stops_df.shape[1]} cols")
print(f"Stop Times: {stop_times_df.shape[0]} rows, {stop_times_df.shape[1]} cols")

# --- calculate trips per stop ---
# grouping to see which stops actually get frequent service
stop_frequency_df = (
    stop_times_df.groupby("stop_id")
    .size()
    .reset_index(name="trip_count")
)

# merge back into main stops dataframe
stops_merged = stops_df.merge(stop_frequency_df, on="stop_id", how="left")
stops_merged["trip_count"] = stops_merged["trip_count"].fillna(0).astype(int)

# --- categorize stop frequency ---
# had to adjust these thresholds after seeing the actual distribution
stops_merged["frequency_category"] = np.select(
    [
        stops_merged["trip_count"] >= 300,
        stops_merged["trip_count"] >= 100,
    ],
    ["High", "Medium"],
    default="Low",
)

print("\n--- trip count stats ---")
print(f"Min:  {stops_merged['trip_count'].min()}")
print(f"Max:  {stops_merged['trip_count'].max()}")
print(f"Mean: {stops_merged['trip_count'].mean():.2f}")

print("\n--- frequency categories ---")
print(stops_merged["frequency_category"].value_counts())

print("\n--- stops merged preview ---")
print(stops_merged.head().to_string())

# --- setup spatial data ---
# convert basic lat/lon to proper geometry points
geometry = [Point(xy) for xy in zip(stops_merged["stop_lon"], stops_merged["stop_lat"])]
stops_gdf = gpd.GeoDataFrame(stops_merged, geometry=geometry, crs="EPSG:4326")

# using Statistics Canada Lambert projection so distances are in actual metres, not degrees
# took me a while to figure out the CRS needs to match before buffering
stops_projected = stops_gdf.to_crs(epsg=3347)

# --- build walkability buffers ---
buffer_400 = stops_projected.copy()
buffer_400["geometry"] = stops_projected.geometry.buffer(400)

buffer_800 = stops_projected.copy()
buffer_800["geometry"] = stops_projected.geometry.buffer(800)

# dissolve merges overlapping buffers so we dont double count coverage areas
coverage_400 = buffer_400.dissolve()
coverage_800 = buffer_800.dissolve()

# project back to standard GPS coordinates for mapping later
coverage_400 = coverage_400.to_crs(epsg=4326)
coverage_800 = coverage_800.to_crs(epsg=4326)

# calculate absolute coverage area in km2
area_400_km2 = coverage_400.to_crs(epsg=3347).geometry.area.sum() / 1e6
area_800_km2 = coverage_800.to_crs(epsg=3347).geometry.area.sum() / 1e6

print("\n--- total network coverage area ---")
print(f"400m walk: {area_400_km2:.2f} km²")
print(f"800m walk: {area_800_km2:.2f} km²")

# --- verification plot: buffers ---
fig, ax = plt.subplots(1, 1, figsize=(10, 10))

coverage_800.plot(ax=ax, color="blue", alpha=0.3, label="800m buffer")
coverage_400.plot(ax=ax, color="darkblue", alpha=0.3, label="400m buffer")
stops_gdf.plot(ax=ax, color="red", markersize=5, label="Stops")

ax.set_title("Transit Stop Coverage – Milton, ON")
ax.legend()
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

plt.tight_layout()
plt.savefig("outputs/buffer_verification.png", dpi=150)
plt.close()
print("\nsaved buffer check plot to outputs/buffer_verification.png")

# --- load municipal borders ---
ontario_municipalities = gpd.read_file(
    "data/Municipal_Boundary_-_Lower_and_Single_Tier/"
    "Municipal_Boundary_-_Lower_and_Single_Tier.shp"
)

# filtering down to just Milton
milton_matches = ontario_municipalities[
    ontario_municipalities["MUNICIPA_2"].str.contains("Milton", case=False, na=False)
]

milton_boundary = ontario_municipalities[
    ontario_municipalities["MUNICIPA_2"].str.contains("Town of Milton", case=False, na=False)
].copy()
milton_boundary = milton_boundary.to_crs(epsg=4326)

print("\n--- boundary filter check ---")
print(f"Found {len(milton_boundary)} exact match for Town of Milton")

# --- load dissemination areas ---
da_boundaries = gpd.read_file("data/lda_000b21a_e/lda_000b21a_e.shp")

# clip DAs to just the ones inside Milton's border
da_boundaries = da_boundaries.to_crs(epsg=4326)
milton_da = gpd.clip(da_boundaries, milton_boundary)

print(f"Total DAs inside Milton: {len(milton_da)}")

# --- verification plot: boundaries ---
fig, ax = plt.subplots(1, 1, figsize=(10, 10))

milton_da.plot(ax=ax, color="lightgreen", edgecolor="grey", linewidth=0.5, label="DA zones")
milton_boundary.boundary.plot(ax=ax, color="black", linewidth=2, label="Milton boundary")

ax.set_title("Milton Boundary & DAs")
ax.legend()
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

plt.tight_layout()
plt.savefig("outputs/boundary_verification.png", dpi=150)
plt.close()
print("saved boundary check plot to outputs/boundary_verification.png")

# --- check for existing population data in shapefile ---
pop_cols = [c for c in milton_da.columns if "pop" in c.lower()]
if not pop_cols:
    print("\nNo population col found in shapefile - will need to join census data later")

# synthetic population fallback using area x density estimate
# this gets replaced entirely once real census data loads below
# only here in case the census join fails for some reason
if "population" not in milton_da.columns:
    milton_da_proj = milton_da.to_crs(epsg=3347)
    milton_da = milton_da.copy()
    milton_da["area_km2"] = milton_da_proj.geometry.area / 1e6
    milton_da["population"] = (milton_da["area_km2"] * 1200).round(0).astype(int)

# --- find the transit deserts ---
# DAs that don't overlap with the 400m walk buffer at all
coverage_400_check = coverage_400.to_crs(milton_da.crs)
# computing once and reusing so we're not dissolving the geometry twice
coverage_union = coverage_400_check.union_all()
served_mask = milton_da.intersects(coverage_union)
desert_zones = milton_da[~served_mask].copy()

# classify how bad the gap is based on size of the population affected
desert_zones["desert_severity"] = np.select(
    [
        desert_zones["population"] > 500,
        desert_zones["population"] >= 200,
    ],
    ["Critical", "Moderate"],
    default="Low Priority",
)

# --- load real census population ---
print("\n--- parsing real census data ---")
census_file = "data/98-401-X2021006_Ontario_eng_CSV/98-401-X2021006_English_CSV_data_Ontario.csv"

# the census file is massive so filtering early saves a lot of memory
chunk_iter = pd.read_csv(
    census_file,
    usecols=["ALT_GEO_CODE", "CHARACTERISTIC_NAME", "C1_COUNT_TOTAL"],
    dtype={"ALT_GEO_CODE": str, "C1_COUNT_TOTAL": str},
    encoding='latin1',
    chunksize=250000
)

milton_dauids = set(milton_da["DAUID"].astype(str))
filtered_chunks = []

print("Extracting Milton DA records...")
for chunk in chunk_iter:
    # grab only the total population metric
    mask_pop = chunk["CHARACTERISTIC_NAME"].fillna("").str.contains("Population, 2021", case=False)
    filtered = chunk[mask_pop]
    
    # filter to only the IDs we care about
    mask_da = filtered["ALT_GEO_CODE"].isin(milton_dauids)
    filtered_chunks.append(filtered[mask_da])

census_df = pd.concat(filtered_chunks, ignore_index=True)

# create a clean dataframe to join
milton_pop = census_df[["ALT_GEO_CODE", "C1_COUNT_TOTAL"]].copy()
milton_pop.columns = ["DAUID", "population"]

# handle missing or suppressed data
milton_pop["population"] = pd.to_numeric(milton_pop["population"], errors="coerce").fillna(0).astype(int)

# --- merge real population and recalculate ---
# chuck out the old synthetic estimate
if "population" in milton_da.columns:
    milton_da = milton_da.drop(columns=["population"])

milton_da = milton_da.merge(milton_pop, on="DAUID", how="left")
milton_da["population"] = milton_da["population"].fillna(0).astype(int)

print(f"\nReal Milton Population: {milton_da['population'].sum():,}")

# run the desert logic one more time with the real numbers
served_mask = milton_da.intersects(coverage_union)
desert_zones = milton_da[~served_mask].copy()

desert_zones["desert_severity"] = np.select(
    [
        desert_zones["population"] > 500,
        desert_zones["population"] >= 200,
    ],
    ["Critical", "Moderate"],
    default="Low Priority",
)

total_pop_milton_real = milton_da["population"].sum()
total_pop_desert_real = desert_zones["population"].sum()
pct_desert_real = (total_pop_desert_real / total_pop_milton_real * 100) if total_pop_milton_real > 0 else 0

print("\n--- final transit desert stats ---")
print(f"Total desert zones: {len(desert_zones)}")
print(f"Population in deserts: {total_pop_desert_real:,}")
print(f"Milton population: {total_pop_milton_real:,}")
print(f"Percentage excluded: {pct_desert_real:.1f}%")

print("\n--- desert severity counts ---")
print(desert_zones["desert_severity"].value_counts())


# --- build interactive map ---
print("\nbuilding folium map...")

m = folium.Map(
    location=[43.5183, -79.8774],
    zoom_start=12,
    tiles="CartoDB positron"
)

# setup layers
fg_boundary = folium.FeatureGroup(name="Milton Boundary")
fg_coverage_800 = folium.FeatureGroup(name="800m Walk Coverage")
fg_coverage_400 = folium.FeatureGroup(name="400m Walk Coverage")
fg_deserts = folium.FeatureGroup(name="Transit Deserts")
fg_stops = folium.FeatureGroup(name="Bus Stops")

# drop datetime stuff before passing to folium or it complains about JSON serialization
milton_boundary_clean = milton_boundary.drop(columns=["EFFECTIVE_", "SYSTEM_DAT"], errors="ignore")

folium.GeoJson(
    milton_boundary_clean,
    style_function=lambda x: {
        "fillOpacity": 0,
        "color": "darkblue",
        "weight": 3
    }
).add_to(fg_boundary)

# population choropleth (adds itself to layer control automatically)
folium.Choropleth(
    geo_data=milton_da,
    data=milton_da,
    columns=["DAUID", "population"],
    key_on="feature.properties.DAUID",
    fill_color="YlOrRd",
    fill_opacity=0.6,
    line_opacity=0.2,
    name="Population Density",
    legend_name="Population per DA"
).add_to(m)

# 800m walkshed
folium.GeoJson(
    coverage_800,
    style_function=lambda x: {
        "fillColor": "lightblue",
        "color": "lightblue",
        "weight": 1,
        "fillOpacity": 0.2
    }
).add_to(fg_coverage_800)

# 400m walkshed
folium.GeoJson(
    coverage_400,
    style_function=lambda x: {
        "fillColor": "blue",
        "color": "blue",
        "weight": 1,
        "fillOpacity": 0.35
    }
).add_to(fg_coverage_400)

# desert zones
def get_desert_color(feature):
    severity = feature["properties"]["desert_severity"]
    if severity == "Critical":
        return "#d73027"
    elif severity == "Moderate":
        return "#fc8d59"
    return "#fee090"

def get_desert_opacity(feature):
    severity = feature["properties"]["desert_severity"]
    if severity == "Critical":
        return 0.65
    elif severity == "Moderate":
        return 0.55
    return 0.3

folium.GeoJson(
    desert_zones,
    style_function=lambda feature: {
        "fillColor": get_desert_color(feature),
        "color": "black",
        "weight": 0.5,
        "fillOpacity": get_desert_opacity(feature)
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["DAUID", "desert_severity", "population"],
        aliases=["DA ID:", "Severity:", "Population:"],
        localize=True
    )
).add_to(fg_deserts)

# bus stops
def get_stop_color(freq):
    if freq == "High":
        return "#1a9641"
    elif freq == "Medium":
        return "#fdae61"
    return "#d7191c"

for idx, row in stops_gdf.iterrows():
    popup_text = f"<b>{row['stop_name']}</b><br>Trips: {row['trip_count']}"
    folium.CircleMarker(
        location=[row["stop_lat"], row["stop_lon"]],
        radius=5,
        color=get_stop_color(row["frequency_category"]),
        fill=True,
        fill_color=get_stop_color(row["frequency_category"]),
        fill_opacity=0.8,
        popup=folium.Popup(popup_text, max_width=300)
    ).add_to(fg_stops)

# map assembly
m.add_child(fg_boundary)
m.add_child(fg_coverage_800)
m.add_child(fg_coverage_400)
m.add_child(fg_deserts)
m.add_child(fg_stops)

folium.LayerControl(collapsed=False).add_to(m)

map_path = "outputs/milton_transit_desert_map.html"
m.save(map_path)
print(f"saved final map to {map_path}")
