from datetime import timedelta

from django import template

from hq.utils import build_url as build_url_util

register = template.Library()

@register.simple_tag
def build_device_url(domain, device_id):
    """Builds the link on the report when you click on the device 
       to get a filtered view of the metadata."""
    return build_url_util("/reports/%s/custom/metadata?filter_deviceid=%s" %\
                          (domain.id, device_id))
    
    
@register.simple_tag
def build_count_url(domain, device_id, date):
    """Builds the link on the report when you click on the device 
       to get a filtered view of the metadata."""
    # this is pretty ugly, but one way to get the URL's working in email 
    day_after_date = date + timedelta(days=1)
    return build_url_util\
        ("/reports/%s/custom/metadata?filter_deviceid=%s&filter_timeend__gte=%s&filter_timeend__lte=%s" \
        % (domain.id, device_id, date, day_after_date))
    
                        