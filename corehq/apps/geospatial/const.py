
GPS_POINT_CASE_PROPERTY = 'gps_point'

ALGO_AES = 'aes'

# Max number of cases per geohash
MAX_GEOHASH_DOC_COUNT = 10_000

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
