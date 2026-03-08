# Milton Transit Desert Analysis

## Overview
I built this project to analyze the spatial equity of public transportation in Milton, Ontario. As one of Canada's fastest-growing municipalities, Milton's rapid suburban expansion made it a fascinating case study for transit accessibility. In this project, a transit desert is defined as a residential area where residents live beyond a reasonable walking distance from any transit stop, effectively excluding them from the network regardless of their need. Using real GTFS stop data and 2021 Census population data, I mapped these transit service coverage gaps to identify which residential zones fall outside standard walkability thresholds of 400m and 800m.

## Key Findings
- 22.9% of Milton residents — approximately 37,670 people — live beyond a 5-minute walk (400m) from any transit stop
- 47 out of 171 Dissemination Areas qualify as transit deserts at the 400m threshold
- At the 800m threshold, Milton's urban core is reasonably well served — the critical gaps are concentrated in fringe residential neighbourhoods on the eastern and southern edges of the urban core
- Transit coverage is heavily corridor-based, following major roads, leaving residents on perpendicular residential streets in walkability gaps despite living close to served areas
- Western Milton DAs show very low population density consistent with rural and agricultural land use — these are not transit planning priorities
- Service frequency within the covered network is strong — 75 stops classified as High frequency and 309 as Medium, suggesting the primary issue is geographic coverage rather than service quality on existing routes

## Methodology

First, GTFS data from Milton Transit was parsed to extract all 414 stops and 121,762 stop-time records. Stop frequency was calculated by counting total trip visits per stop and categorized into High (300+ trips), Medium (100-299 trips), and Low (under 100 trips) tiers. One unexpected challenge here was that my initial trip count thresholds were way too low, and I had to adjust them significantly after seeing the real distribution of service frequency to get meaningful categories.

Next, service coverage was modeled using 400m and 800m Euclidean buffers around each stop, representing 5-minute and 10-minute walking thresholds respectively — the standard benchmarks used in transit planning practice. Buffers were dissolved using GeoPandas to eliminate double-counting of overlapping coverage areas, producing a unified coverage polygon for each threshold. This was my first time working extensively with GIS data operations in Python, and handling Coordinate Reference System (CRS) reprojections for accurate distance buffering proved to be a valuable learning experience. 

To identify transit deserts, I spatially subtracted the 400m coverage polygon from Milton's 171 Dissemination Areas. Any DA whose geometry did not intersect the coverage polygon was classified as a desert zone. Population figures from the 2021 Statistics Canada Census Profile were then joined to each DA by DAUID to calculate real residential population in desert zones. Extracting and merging the Census population data required matching DAUIDs carefully across two massive, entirely different data sources, which took some creative Pandas chunking and filtering to do efficiently on my device.

Limitations: While Euclidean straight-line distances are useful baselines, they do not account for physical barriers such as highways, fences, or ravines — a network-based walkshed analysis would produce more precise results. Second, the DA-level population data assigns a single population figure to each zone, which may mask internal variation in where residents actually live within a large DA. Third, this analysis uses a static GTFS snapshot and does not account for seasonal schedule changes or real-time service reliability.

## Data Sources
- Milton Transit GTFS Static Feed — miltontransit.ca
- Statistics Canada 2021 Census Profile — Dissemination Area level, Ontario
- Ontario Municipal Boundary — Lower and Single Tier, Land Information Ontario GeoHub

## Tech Stack
Python, GeoPandas, Folium, Pandas, Shapely, NumPy, Matplotlib, Statistics Canada 2021 Census

## What I Would Do Next
- Replace Euclidean buffers with network-based walksheds using OSMnx to account for the actual street network and pedestrian routing barriers.
- Incorporate actual ridership data, if Milton Transit makes it available, to understand how coverage correlates with usage.
- Extend the analysis to compare Milton's coverage ratio against other fast-growing Ontario municipalities like Brampton or Waterloo.

## How to Run

1. Clone the repository
2. Run `pip install -r requirements.txt`
3. Place the three data sources in the `data/` folder as described in Data Sources
4. Run `python analysis.py`

The output map will be saved to `outputs/milton_transit_desert_map.html`.
