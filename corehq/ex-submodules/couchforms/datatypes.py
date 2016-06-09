from collections import namedtuple


class GeoPoint(namedtuple('GeoPoint', 'latitude longitude altitude accuracy')):
    @property
    def lat_long(self):
        return {
            'lat': self.latitude,
            'lon': self.longitude
        }
