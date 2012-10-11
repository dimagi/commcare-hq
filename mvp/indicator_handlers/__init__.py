import datetime
from dimagi.utils.dates import DateSpan

class IndicatorHandler(object):

    def __init__(self, domain, user_ids, datespan):
        """
            domain should be the domain name
            users should be a list of user_ids or a single user id to compute these indicators.
        """
        if not isinstance(datespan, DateSpan):
            raise ValueError("datespan must be a DateSpan")
        self.domain = domain
        if not isinstance(user_ids, list):
            user_ids = [user_ids]
        self.user_ids = user_ids
        self.datespan = datespan

    @property
    def indicators(self):
        return NotImplementedError