from __future__ import absolute_import
from __future__ import unicode_literals
import json

DEFAULT_DISPLAY_LENGTH = "10"
DEFAULT_START = "0"
DEFAULT_ECHO = "0"


class DatatablesParams(object):

    def __init__(self, count, start, desc, echo, search=None):
        self.count = count
        self.start = start
        self.desc = desc
        self.echo = echo
        self.search = search

    def __repr__(self):
        return json.dumps({
            'start': self.start,
            'count': self.count,
            'echo': self.echo,
        }, indent=2)

    @classmethod
    def from_request_dict(cls, query):

        count = int(query.get("iDisplayLength", DEFAULT_DISPLAY_LENGTH))

        start = int(query.get("iDisplayStart", DEFAULT_START))

        # sorting
        desc_str = query.get("sSortDir_0", "desc")
        desc = desc_str == "desc"

        echo = query.get("sEcho", DEFAULT_ECHO)

        search = query.get("sSearch", "")

        return DatatablesParams(count, start, desc, echo, search)
