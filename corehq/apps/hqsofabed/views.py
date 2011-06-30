# stub views file
from corehq.apps.domain.decorators import login_and_domain_required
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from corehq.apps.hqsofabed.models import HQFormData
from .tables import HQFormDataTable

@login_and_domain_required
def formlist(request, domain):
    
    form_list = HQFormData.objects.filter(domain=domain)
    return render_to_response("hqsofabed/formlist.html", 
                              {"form_table": HQFormDataTable(form_list, request=request)}, 
                              context_instance=RequestContext(request))