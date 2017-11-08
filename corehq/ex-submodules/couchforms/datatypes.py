from __future__ import absolute_import
from collections import namedtuple


class GeoPoint(namedtuple('GeoPoint', 'latitude longitude altitude accuracy')):
    @property
    def lat_lon(self):
        return {
            'lat': self.latitude,
            'lon': self.longitude
        }
