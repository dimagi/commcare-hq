from django.template.loader import render_to_string

import settings 

from xformmanager.models import Metadata
from hq.utils import paginate, get_table_display_properties, get_query_set


def metadata(request, domain=None):
    '''Submission Summary List for All Forms'''
    if not domain:
        domain = request.user.selected_domain
    # extract params from the URL
    
    items, sort_column, sort_descending, filters =\
         get_table_display_properties(request)
    filters["attachment__submission__domain"] = domain
    columns = [["formdefmodel", "Form"],
               ["deviceid", "Device"],
               ["chw_id", "User Id"],
               ["username", "User Name"],
               ["timestart", "Started"],
               ["timeend", "Ended"]]

    all_meta = get_query_set(Metadata, sort_column, sort_descending, filters)
    paginated_meta = paginate(request, all_meta, items)
    return render_to_string("custom/all/metadata.html", 
                            {"MEDIA_URL": settings.MEDIA_URL, # we pretty sneakly have to explicitly pass this
                             "columns": columns, 
                             "all_metadata": paginated_meta,
                             "sort_column": sort_column,
                             "sort_descending": sort_descending,
                             "filters": filters })
