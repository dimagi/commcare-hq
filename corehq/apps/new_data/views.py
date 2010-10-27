from couchforms.models import XFormInstance
from corehq.util.webutils import render_to_response
from django.http import HttpResponse
from couchexport.export import export_excel
from StringIO import StringIO
from corehq.apps.domain.decorators import login_and_domain_required

def data(req, domain, template="new_data/data.html"):
    instances = XFormInstance.view('new_data/xforminstances', startkey=[domain], endkey=[domain, {}]).all()
    print instances
    return render_to_response(req, template, {
        'tab': 'data',
        'domain': domain,
        'instances': instances,
    })

@login_and_domain_required
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    export_tag = req.GET.get("export_tag", "")
    if not export_tag:
        raise Exception("You must specify a model to download!")
    tmp = StringIO()
    if export_excel([domain, export_tag], tmp):
        response = HttpResponse(mimetype='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % export_tag
        response.write(tmp.getvalue())
        tmp.close()
        return response
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)
