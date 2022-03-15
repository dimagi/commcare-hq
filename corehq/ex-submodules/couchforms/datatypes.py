from collections import namedtuple


class GeoPoint(namedtuple('GeoPoint', 'latitude longitude altitude accuracy')):
    @property
    def lat_lon(self):
        # suitable to send to an elasticsearch geo_point field
        return {
            'lat': self.latitude,
            'lon': self.longitude
        }
