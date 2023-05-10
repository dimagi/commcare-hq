class GeoSpatialException(Exception):
    pass


class InvalidCoordinate(GeoSpatialException):
    """Raised when an invalid lat/lon coordinate is given"""
    message = "Invalid lat/lon co-ordinate given"

    def __init__(self, msg=None, *args, **kwargs):
        if msg:
            self.message = msg
        super().__init__(self.message, *args, **kwargs)


class InvalidDistributionParam(GeoSpatialException):
    pass
