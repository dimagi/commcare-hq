# Create your views here.
from dimagi.utils.web import render_to_response
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

def index(request, domain, topic):
    template = "help/%s.html" % topic

    return render_to_response(request, template, {
        'domain': domain,
    })

def default(request, domain):
    return HttpResponseRedirect(reverse('corehq.apps.help.views.index', args=[domain, 'getting-started']))