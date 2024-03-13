from urllib.error import URLError


class Format(object):
    """
    Supported formats go here.
    """
    CSV = "csv"
    ZIP = "zip"
    XLS = "xls"
    XLS_2007 = "xlsx"
    HTML = "html"
    ZIPPED_HTML = "zipped-html"
    JSON = "json"
    PYTHON_DICT = "dict"
    UNZIPPED_CSV = 'unzipped-csv'
    GEOJSON = 'geojson'

    FORMAT_DICT = {CSV: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   ZIP: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   XLS: {"mimetype": "application/vnd.ms-excel",
                         "extension": "xls",
                         "download": True},
                   XLS_2007: {"mimetype": "application/vnd.ms-excel",
                              "extension": "xlsx",
                              "download": True},
                   HTML: {"mimetype": "text/html; charset=utf-8",
                          "extension": "html",
                          "download": False},
                   ZIPPED_HTML: {"mimetype": "application/zip",
                                 "extension": "zip",
                                 "download": True},
                   JSON: {"mimetype": "application/json",
                          "extension": "json",
                          "download": False},
                   PYTHON_DICT: {"mimetype": None,
                          "extension": None,
                          "download": False},
                   UNZIPPED_CSV: {"mimetype": "text/csv",
                                  "extension": "csv",
                                  "download": True},
                   GEOJSON: {"mimetype": "application/geo+json",
                          "extension": "geojson",
                          "download": True},
                   }

    VALID_FORMATS = list(FORMAT_DICT)

    def __init__(self, slug, mimetype, extension, download):
        self.slug = slug
        self.mimetype = mimetype
        self.extension = extension
        self.download = download

    @classmethod
    def from_format(cls, format):
        format = format.lower()
        if format not in cls.VALID_FORMATS:
            raise URLError("Unsupported export format: %s!" % format)
        return cls(format, **cls.FORMAT_DICT[format])


class IntegrationFormat(object):
    LIVE_GOOGLE_SHEETS = "live_google_sheets"

    VALID_FORMATS = [
        LIVE_GOOGLE_SHEETS,
    ]

    @classmethod
    def is_integration_format(cls, format):
        format = format.lower()
        if format in cls.VALID_FORMATS:
            return True
        return False
