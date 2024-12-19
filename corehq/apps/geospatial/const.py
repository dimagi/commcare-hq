
GPS_POINT_CASE_PROPERTY = 'gps_point'

ALGO_AES = 'aes'

# Max number of cases per geohash
MAX_GEOHASH_DOC_COUNT = 1_000

# Travel modes
TRAVEL_MODE_WALKING = "walking"
TRAVEL_MODE_CYCLING = "cycling"
TRAVEL_MODE_DRIVING = "driving"

# Modified version of https://geojson.org/schema/FeatureCollection.json
#   Modification 1 - Added top-level name attribute
#   Modification 2 - geometry is limited to a polygon
POLYGON_COLLECTION_GEOJSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://geojson.org/schema/FeatureCollection.json",
    "title": "GeoJSON FeatureCollection",
    "type": "object",
    "required": [
        "type",
        "features",
        # Modification 1 - Added top-level name attribute
        "name",
    ],
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "FeatureCollection"
            ]
        },
        "name": {
            "type": "string"
        },
        "features": {
            "type": "array",
            "items": {
                "title": "GeoJSON Feature",
                "type": "object",
                "required": [
                    "type",
                    "properties",
                    "geometry"
                ],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "Feature"
                        ]
                    },
                    "id": {
                        "oneOf": [
                            {
                                "type": "number"
                            },
                            {
                                "type": "string"
                            }
                        ]
                    },
                    "properties": {
                        "oneOf": [
                            {
                                "type": "null"
                            },
                            {
                                "type": "object"
                            }
                        ]
                    },
                    # Modification 2 - geometry is limited to a polygon
                    "geometry": {
                        "oneOf": [
                            {
                                "title": "GeoJSON Polygon",
                                "type": "object",
                                "required": [
                                    "type",
                                    "coordinates"
                                ],
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "Polygon"
                                        ]
                                    },
                                    "coordinates": {
                                        "type": "array",
                                        "items": {
                                            "type": "array",
                                            "minItems": 4,
                                            "items": {
                                                "type": "array",
                                                "minItems": 2,
                                                "items": {
                                                    "type": "number"
                                                }
                                            }
                                        }
                                    },
                                    "bbox": {
                                        "type": "array",
                                        "minItems": 4,
                                        "items": {
                                            "type": "number"
                                        }
                                    }
                                }
                            }
                        ]
                    },
                    "bbox": {
                        "type": "array",
                        "minItems": 4,
                        "items": {
                            "type": "number"
                        }
                    }
                }
            }
        },
        "bbox": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "number"
            }
        }
    }
}

# Case property to identify cases assigned through disbursement on the Case Management Page
ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY = 'commcare_assigned_via_disbursement'
ES_INDEX_TASK_HELPER_BASE_KEY = 'geo_cases_index_cases'

DEFAULT_QUERY_LIMIT = 10_000
DEFAULT_CHUNK_SIZE = 100
