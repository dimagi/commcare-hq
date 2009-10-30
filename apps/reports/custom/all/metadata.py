from django.template.loader import render_to_string

from xformmanager.models import Metadata
from hq.utils import paginate, get_table_display_properties, get_query_set


def metadata(request, domain=None):
    '''Submission Summary List for All Forms'''
    if not domain:
        domain = request.extuser.domain
    # extract params from the URL
    
    items, sort_column, sort_descending, filters =\
         get_table_display_properties(request)
    filters["attachment__submission__domain"] = domain
    
    all_meta = get_query_set(Metadata, sort_column, sort_descending, filters)
    paginated_meta = paginate(request, all_meta)
    return render_to_string("custom/all/metadata.html", 
                            {"all_metadata": paginated_meta })
