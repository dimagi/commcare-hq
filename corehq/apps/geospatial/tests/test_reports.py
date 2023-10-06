from nose.tools import assert_equal

from ..reports import geojson_to_es_geoshape


def test_geojson_to_es_geoshape():
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [125.6, 10.1]
        },
        "properties": {
            "name": "Dinagat Islands"
        }
    }
    es_geoshape = geojson_to_es_geoshape(geojson)
    assert_equal(es_geoshape, {
        "type": "point",  # NOTE: lowercase Elasticsearch type
        "coordinates": [125.6, 10.1]
    })
