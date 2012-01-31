from datetime import datetime
from pytz import timezone
import settings

def make_time():
    return datetime.now(tz=timezone(settings.TIME_ZONE))