from couchforms.views import post as couchforms_post
from django.http import HttpResponse
from corehq.util.webutils import render_to_response
from .forms import RegisterXForm
from .models import XForm
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
from collections import defaultdict

def post(request):
    def callback(doc):
        doc['submit_ip'] = request.META['REMOTE_ADDR']
        #doc['domain'] = request.user.selected_domain()
        doc.save()
        return HttpResponse("%s\n" % doc['_id'])
    return couchforms_post(request, callback)

def dashboard(request, template='new_xforms/register_xform.html'):
    domain = request.user.selected_domain.name
    if(len(request.FILES) == 1):
        for name in request.FILES:
            doc = _register_xform(
                attachment=request.FILES[name],
                display_name=request.POST.get('form_display_name', ''),
                domain=domain
            )

    xforms = XForm.view('new_xforms/by_domain', startkey=[domain], endkey=[domain, {}]).all()
    by_xmlns = defaultdict(list)
    for xform in xforms:
        by_xmlns[xform.xmlns].append(xform)
    form_groups = []
    for _, forms in by_xmlns.items():
        fg = {}
        for attr in ('xmlns', 'display_name', 'domain'):
            fg[attr] = forms[-1][attr]
        fg['forms'] = forms
        fg['first_date_registered'] = forms[0].submit_time
        form_groups.append(fg)

    return render_to_response(request, template, {
        'upload_form': RegisterXForm(),
        'form_groups': form_groups
    })


def _register_xform(display_name, attachment, domain):
    if not isinstance(attachment, basestring):
        attachment = attachment.read()
    doc = XForm()
    doc.display_name = display_name
    soup = BeautifulStoneSoup(attachment)
    doc.xmlns = soup.find('instance').findChild()['xmlns']

    doc.submit_time = datetime.utcnow()
    doc.domain = domain

    doc.save()
    doc.put_attachment(attachment, 'xform.xml', content_type='text/xml')
    return doc