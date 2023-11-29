Geospatial Features
===================

Geospatial features allow the management of cases and mobile workers
based on their geographical location. Case location is stored in a
configurable case property, which defaults to "gps_point". Mobile
worker location is stored in user data, also with the name "gps_point".


Case Grouping
-------------

There are various configuration settings available for deciding how case
grouping is done. These parameters are saved in the `GeoConfig` model
which is linked to a domain. It is important to note however, that not
all available parameters will be used for case grouping. The parameters
that actually get used is determined by the chosen grouping method.
Mainly, these are:

1. Min/Max Grouping - Grouping is done by specifying the minimum and
   maximum number of cases that each group may have.

2. Target Size Grouping - Grouping is done by specifying how many groups
   should be created. Cases will then evenly get distributed into groups
   to meet the target number of groups.


CaseGroupingReport pagination
-----------------------------

The `CaseGroupingReport` class uses Elasticsearch
[GeoHash Grid Aggregation][1] to group cases into buckets.

Elasticsearch [bucket aggregations][2] create buckets of documents,
where each bucket corresponds to a property that determines whether a
document falls into that bucket.

The buckets of GeoHash Grid Aggregation are cells in a grid. Each cell
has a GeoHash, which is like a ZIP code or a postal code, in that it
represents a geographical area. If a document's GeoPoint is in a
GeoHash's geographical area, then Elasticsearch places it in the
corresponding bucket. For more information on GeoHash grid cells, see
the Elasticsearch docs on [GeoHash cell dimensions][3].

GeoHash Grid Aggregation buckets look like this:
```
[
    {
        "key": "u17",
        "doc_count": 3
    },
    {
        "key": "u09",
        "doc_count": 2
    },
    {
        "key": "u15",
        "doc_count": 1
    }
]
```
In this example, "key" is a GeoHash of length 3, and "doc_count" gives
the number of documents in each bucket, or GeoHash grid cell.

For `CaseGroupingReport`, buckets are pages. So pagination simply flips
from one bucket to the next.


Setting Up Test Data
--------------------

To populate test data for any domain, you could simply do a bulk upload
for cases with the following columns

1. case_id: Blank for new cases

2. name: (Optional) Add a name for each case. Remove column if not using

3. gps_point: GPS coordinate for the case that has latitude, longitude,
   altitude and accuracy separated by an empty space. Example:
   `9.9999952 3.2859413 393.2 4.36`. This is the case property saved on
   a case to capture its location and is configurable with default
   value being `gps_point`, so good to check Geospatial Configuration
   Settings page for the project to confirm the case property being
   used before doing the upload. If its different, then this column
   should use that case property instead of `gps_point`

4. owner_name: (Optional) To assign case to a mobile worker, simply add
   worker username here. Remove column if not using.

For Dimagi devs looking for bulk data, you could use any of the Excel
sheets available in Jira ticket [SC-3051][4].

MapBox Streets V8 Tiles
{
	"vector_layers": [
		{
			"description": "",
			"fields": {
				"class": "One of: aboriginal_lands, agriculture, airport, cemetery, commercial_area, facility, glacier, grass, hospital, industrial, park, parking, piste, pitch, residential, rock, sand, school, scrub, wood",
				"type": "OSM tag, more specific than class"
			},
			"id": "landuse",
			"minzoom": 5,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: river, canal, stream, stream_intermittent, ditch, drain",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"type": "One of: river, canal, stream, ditch, drain"
			},
			"id": "waterway",
			"minzoom": 7,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {},
			"id": "water",
			"minzoom": 0,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"ref": "Text. Identifier of the runway or taxiway",
				"type": "One of: runway, taxiway, apron, helipad"
			},
			"id": "aeroway",
			"minzoom": 9,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: cliff, crosswalk, entrance, fence, gate, hedge, land",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"type": "The value of either the 'barrier' or 'man_made' tag from OSM, or for cliffs either cliff or earth_bank."
			},
			"id": "structure",
			"minzoom": 13,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"extrude": "String. Whether building should be extruded when rendering in 3D. One of: 'true', 'false'",
				"height": "Number. Height of building or part of building.",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"min_height": "Number. Height of bottom of building or part of building, if it does not start at ground level.",
				"type": "In most cases, values will be that of the primary key from OpenStreetMap tags.",
				"underground": "Text. Whether building is underground. One of: 'true', 'false'"
			},
			"id": "building",
			"minzoom": 12,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: national_park, wetland, wetland_noveg",
				"type": "OSM tag, more specific than class"
			},
			"id": "landuse_overlay",
			"minzoom": 5,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"bike_lane": "Text. Has a value if there is a bike lane that is part of the road itself. This is different from a separated cycle track, which will be shown as its own line. Possible values are 'right', 'left', 'both' (bike lane on right, left, or both sides of the street respectively), 'yes' (bike lane present but location not specified), 'no' (area was surveyed and confirmed to not have a bike lane), and null (presence of bike lane unknown).",
				"class": "One of: 'motorway', 'motorway_link', 'trunk', 'primary', 'secondary', 'tertiary', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link', 'street', 'street_limited', 'pedestrian', 'construction', 'track', 'service', 'ferry', 'path', 'golf', 'level_crossing', 'turning_circle', 'roundabout', 'mini_roundabout', 'turning_loop', 'traffic_signals'",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"lane_count": "Number. Number of lanes in the road",
				"layer": "Number. Specifies z-ordering in the case of overlapping road segments. Common range is -5 to 5. Available from zoom level 13+.",
				"len": "Number. Approximate length of the road segment in Mercator meters.",
				"name": "Local name of the road",
				"name_ar": "Arabic name of the road",
				"name_de": "German name of the road",
				"name_en": "English name of the road",
				"name_es": "Spanish name of the road",
				"name_fr": "French name of the road",
				"name_it": "Italian name of the road",
				"name_ja": "Japanese name of the road",
				"name_ko": "Korean name of the road",
				"name_pt": "Portuguese name of the road",
				"name_ru": "Russian name of the road",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the road",
				"name_zh-Hans": "Simplified Chinese name of the road",
				"name_zh-Hant": "Traditional Chinese name of the road",
				"oneway": "Text. Whether traffic on the road is one-way. One of: 'true', 'false'.",
				"ref": "Text. Route number/code of the road.",
				"reflen": "Number. How many characters long the ref tag is. Useful for shield styling.",
				"shield": "Text. The shield style to use. See the vector tile documentation for a list of possible values.",
				"shield_beta": "Text. The shield style to use if it doesn't exist in default shield values.",
				"shield_text_color": "Text. The color of the text to use on the highway shield.",
				"shield_text_color_beta": "Text. The color of the text to use on the beta highway shield.",
				"structure": "Text. One of: 'none', 'bridge', 'tunnel', 'ford'. Available from zoom level 13+.",
				"surface": "Whether the road is paved or not (if known). One of: 'paved', 'unpaved'",
				"toll": "Whether a road is a toll road or not.",
				"type": "In most cases, values will be that of the primary key from OpenStreetMap tags."
			},
			"id": "road",
			"minzoom": 3,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"admin_level": "Number, 0-2. The administrative level of the boundary",
				"disputed": "Disputed boundaries are 'true', all others are 'false'.",
				"iso_3166_1": "The ISO 3166-1 alpha-2 code(s) of the state(s) a boundary is part of. Format: 'AA' or 'AA-BB'",
				"maritime": "Maritime boundaries are 'true', all others are 'false'.",
				"worldview": "One of 'all', 'CN', 'IN', 'US'. Use for filtering boundaries to match different worldviews."
			},
			"id": "admin",
			"minzoom": 0,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"abbr": "Text. Local abbreviation of the place (available for type=state).",
				"capital": "Admin level the city is a capital of, if any. One of: 2, 3, 4, 5, 6, null",
				"class": "One of: country, state, settlement, or settlement_subdivision",
				"filterrank": "Number, 0-5. Priority relative to nearby places. Useful for limiting label density.",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the place.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the road is in.",
				"name": "Local name of the place",
				"name_ar": "Arabic name of the place",
				"name_de": "German name of the place",
				"name_en": "English name of the place",
				"name_es": "Spanish name of the place",
				"name_fr": "French name of the place",
				"name_it": "Italian name of the place",
				"name_ja": "Japanese name of the place",
				"name_ko": "Korean name of the place",
				"name_pt": "Portuguese name of the place",
				"name_ru": "Russian name of the place",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the place",
				"name_zh-Hans": "Simplified Chinese name of the place",
				"name_zh-Hant": "Traditional Chinese name of the place",
				"symbolrank": "Number, 1-18. Useful for styling text & marker sizes.",
				"text_anchor": "A hint for label placement at low zoom levels.",
				"type": "One of: country, territory, sar, disputed_territory, state, city, town, village, hamlet, suburb, quarter, neighbourhood, island, islet, archipelago, residential, aboriginal_lands",
				"worldview": "One of 'all', 'CN', 'IN', 'US'. Use for filtering boundaries to match different worldviews."
			},
			"id": "place_label",
			"minzoom": 0,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: military, civil",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"maki": "One of: airport, heliport, rocket",
				"name": "Local name of the airport",
				"name_ar": "Arabic name of the airport",
				"name_de": "German name of the airport",
				"name_en": "English name of the airport",
				"name_es": "Spanish name of the airport",
				"name_fr": "French name of the airport",
				"name_it": "Italian name of the airport",
				"name_ja": "Japanese name of the airport",
				"name_ko": "Korean name of the airport",
				"name_pt": "Portuguese name of the airport",
				"name_ru": "Russian name of the airport",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the airport",
				"name_zh-Hans": "Simplified Chinese name of the airport",
				"name_zh-Hant": "Traditional Chinese name of the airport",
				"ref": "A 3-4 character IATA, FAA, ICAO, or other reference code",
				"sizerank": "A scale-dependent feature size ranking from 0 (large) to 16 (small)",
				"worldview": "One of 'all', 'CN', 'IN', 'US'. Use for filtering boundaries to match different worldviews."
			},
			"id": "airport_label",
			"minzoom": 8,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"filterrank": "Number, 0-5. Priority relative to nearby features. Useful for limiting label density.",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"maki": "One of: rail, rail-metro, rail-light, entrance, bus, bicycle-share, ferry",
				"mode": "One of: rail, metro_rail, light_rail, tram, bus, monorail, funicular, bicycle, ferry, narrow_gauge, preserved, miniature",
				"name": "Local name of the transit stop",
				"name_ar": "Arabic name of the transit stop",
				"name_de": "German name of the transit stop",
				"name_en": "English name of the transit stop",
				"name_es": "Spanish name of the transit stop",
				"name_fr": "French name of the transit stop",
				"name_it": "Italian name of the transit stop",
				"name_ja": "Japanese name of the transit stop",
				"name_ko": "Korean name of the transit stop",
				"name_pt": "Portuguese name of the transit stop",
				"name_ru": "Russian name of the transit stop",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the transit stop",
				"name_zh-Hans": "Simplified Chinese name of the transit stop",
				"name_zh-Hant": "Traditional Chinese name of the transit stop",
				"network": "The network(s) that the station serves. Useful for icon styling.",
				"network_beta": "One of: jp-shinkansen, jp-shinkansen.jp-jr, jp-shinkansen.tokyo-metro, jp-shinkansen.osaka-subway, jp-shinkansen.jp-jr.tokyo-metro, jp-shinkansen.jp-jr.osaka-subway, jp-jr, jp-jr.tokyo-metro, jp-jr.osaka-subway",
				"stop_type": "One of: station, stop, entrance"
			},
			"id": "transit_stop_label",
			"minzoom": 5,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: glacier, landform, water_feature, wetland, ocean, sea, river, water, reservoir, dock, canal, drain, ditch, stream, continent",
				"elevation_ft": "Integer elevation in feet",
				"elevation_m": "Integer elevation in meters",
				"filterrank": "Number, 0-5. Priority relative to nearby features. Useful for limiting label density.",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"maki": "One of: 'mountain', 'volcano', 'waterfall'",
				"name": "Local name of the natural feature",
				"name_ar": "Arabic name of the natural feature",
				"name_de": "German name of the natural feature",
				"name_en": "English name of the natural feature",
				"name_es": "Spanish name of the natural feature",
				"name_fr": "French name of the natural feature",
				"name_it": "Italian name of the natural feature",
				"name_ja": "Japanese name of the natural feature",
				"name_ko": "Korean name of the natural feature",
				"name_pt": "Portuguese name of the natural feature",
				"name_ru": "Russian name of the natural feature",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the natural feature",
				"name_zh-Hans": "Simplified Chinese name of the natural feature",
				"name_zh-Hant": "Traditional Chinese name of the natural feature",
				"sizerank": "A scale-dependent feature size ranking from 0 (large) to 16 (small)",
				"worldview": "One of 'all', 'CN', 'IN', 'US'. Use for filtering boundaries to match different worldviews."
			},
			"id": "natural_label",
			"minzoom": 0,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"brand": "String",
				"category_en": "English category description of the POI",
				"category_zh-Hans": "Simplified Chinese category description of the POI",
				"class": "Text. Thematic groupings of POIs for filtering & styling.",
				"filterrank": "Number, 0-5. Priority relative to nearby POIs. Useful for limiting label density.",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"maki": "The name of the Maki icon that should be used for the POI",
				"maki_beta": "",
				"maki_modifier": "",
				"name": "Local name of the POI",
				"name_ar": "Arabic name of the POI",
				"name_de": "German name of the POI",
				"name_en": "English name of the POI",
				"name_es": "Spanish name of the POI",
				"name_fr": "French name of the POI",
				"name_it": "Italian name of the POI",
				"name_ja": "Japanese name of the POI",
				"name_ko": "Korean name of the POI",
				"name_pt": "Portuguese name of the POI",
				"name_ru": "Russian name of the POI",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the POI",
				"name_zh-Hans": "Simplified Chinese name of the POI",
				"name_zh-Hant": "Traditional Chinese name of the POI",
				"sizerank": "A scale-dependent feature size ranking from 0 (large) to 16 (small)",
				"type": "The original OSM tag value"
			},
			"id": "poi_label",
			"minzoom": 6,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"class": "The class of road the junction is on. Subset of classes in the road layer. One of: motorway, motorway_link, trunk, trunk_link, primary, secondary, tertiary, primary_link, secondary_link, tertiary_link, street, street_limited, construction, track, service, path, major_rail, minor_rail, service_rail.",
				"filterrank": "Number, 0-5",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in.",
				"maki_beta": "",
				"name": "Local name of the motorway junction",
				"name_ar": "Arabic name of the motorway junction",
				"name_de": "German name of the motorway junction",
				"name_en": "English name of the motorway junction",
				"name_es": "Spanish name of the motorway junction",
				"name_fr": "French name of the motorway junction",
				"name_it": "Italian name of the motorway junction",
				"name_ja": "Japanese name of the motorway junction",
				"name_ko": "Korean name of the motorway junction",
				"name_pt": "Portuguese name of the motorway junction",
				"name_ru": "Russian name of the motorway junction",
				"name_script": "Primary written script of the local name",
				"name_vi": "Vietnamese name of the motorway junction",
				"name_zh-Hans": "Simplified Chinese name of the motorway junction",
				"name_zh-Hant": "Traditional Chinese name of the motorway junction",
				"ref": "A short identifier",
				"reflen": "The number of characters in the ref field.",
				"type": "The type of road the junction is on. Subset of types in the road layer."
			},
			"id": "motorway_junction",
			"minzoom": 9,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "",
			"fields": {
				"house_num": "House number",
				"iso_3166_1": "Text. The ISO 3166-1 alpha-2 code of the country/territory the feature is in.",
				"iso_3166_2": "Text. The ISO 3166-2 code of the state/province/region the feature is in."
			},
			"id": "housenum_label",
			"minzoom": 16,
			"source": "mapbox.mapbox-streets-v8",
			"source_name": "Mapbox Streets v8"
		},
		{
			"description": "Generalized landcover classification",
			"fields": {
				"class": "One of: wood, scrub, grass, crop, snow"
			},
			"id": "landcover",
			"maxzoom": 22,
			"minzoom": 0,
			"source": "mapbox.mapbox-terrain-v2",
			"source_name": "Mapbox Terrain v2"
		},
		{
			"description": "",
			"fields": {
				"class": "One of: shadow, highlight",
				"level": "Brightness %. One of: 94, 90, 89, 78, 67, 56"
			},
			"id": "hillshade",
			"maxzoom": 22,
			"minzoom": 0,
			"source": "mapbox.mapbox-terrain-v2",
			"source_name": "Mapbox Terrain v2"
		},
		{
			"description": "Elevation contour polygons",
			"fields": {
				"ele": "Integer. The elevation of the contour in meters",
				"index": "Indicator for every 2nd, 5th, or 10th contour. Coastlines are given -1. One of: 2, 5, 10, -1, null"
			},
			"id": "contour",
			"maxzoom": 22,
			"minzoom": 0,
			"source": "mapbox.mapbox-terrain-v2",
			"source_name": "Mapbox Terrain v2"
		},
		{
			"fields": {
				"min_depth": "integer"
			},
			"id": "depth",
			"maxzoom": 7,
			"minzoom": 0,
			"source": "mapbox.mapbox-bathymetry-v2",
			"source_name": "Mapbox Bathymetry v2"
		}
	]
}


[1]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html
[2]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket.html
[3]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html#_cell_dimensions_at_the_equator
[4]: https://dimagi-dev.atlassian.net/browse/SC-3051
