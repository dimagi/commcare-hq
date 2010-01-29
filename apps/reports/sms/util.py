"""
Utility functions for custom reports
"""
from datetime import datetime, timedelta
from xformmanager.models import Metadata

def forms_submitted(chw_username, days=0, weeks=0, hours=0):
    """Returns a count of the number of forms submitted over the given timeframe
       Timeframe - the period of time during which these forms were submitted
    """
    metas = Metadata.objects.filter(username=chw_username)
    delta = timedelta(days=days, weeks=weeks, hours=hours)
    since = datetime.today() - delta
    metas = metas.filter(attachment__submission__submit_time__gte=since)
    return metas.count()


