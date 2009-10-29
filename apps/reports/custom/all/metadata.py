from django.template.loader import render_to_string

from xformmanager.models import Metadata
from hq.utils import paginate


def metadata(request, domain=None):
    '''Submission Summary List for All Forms'''
    if not domain:
        domain = request.extuser.domain
    all_meta = Metadata.objects.filter(attachment__submission__domain=domain)
    paginated_meta = paginate(request, all_meta)
    
    return render_to_string("custom/all/metadata.html", 
                            {"all_metadata": paginated_meta })
