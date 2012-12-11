from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from corehq.apps.domain.decorators import require_superuser
from django.views.decorators.http import require_POST
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.management.commands import bootstrap_psi
import bulk
import json
from soil.util import expose_download
import uuid
from django.core.urlresolvers import reverse
from django.contrib import messages
from corehq.apps.commtrack.tasks import import_locations_async

@require_superuser
def bootstrap(request, domain):
    if request.method == "POST":
        D = Domain.get_by_name(domain)
        if D.commtrack_enabled:
            return HttpResponse('already configured', 'text/plain')
        else:
            bootstrap_psi.one_time_setup(D)
            return HttpResponse('set up successfully', 'text/plain')

    return HttpResponse('<form method="post" action=""><button type="submit">Bootstrap Commtrack domain</button></form>')

@require_superuser
def location_import(request, domain):
    if request.method == "POST":
        # stash content in the default storage for subsequent views
        # ret = list(bulk.import_locations(domain, request.FILES['locs']))
        file_ref = expose_download(request.FILES['locs'].read(),
                                   expiry=1*60*60)
        download_id = uuid.uuid4().hex
        import_locations_async.delay(download_id, domain, file_ref.download_id)
        messages.success(request,
            'Your upload is in progress. You can check the progress <a href="%s">here</a>.' %\
            (reverse('hq_soil_download', kwargs={'domain': domain, 'download_id': download_id})),
            extra_tags="html")
        return HttpResponseRedirect(reverse('domain_homepage', args=[domain]))

    return HttpResponse("""
<form method="post" action="" enctype="multipart/form-data">
  <div><input type="file" name="locs" /></div>
  <div><button type="submit">Import locations</button></div>
</form>
""")

@require_superuser
def historical_import(request, domain):
    if request.method == "POST":
        try:
            result = bulk.import_stock_reports(domain, request.FILES['history'])
            resp = HttpResponse(result, 'text/csv')
            resp['Content-Disposition'] = 'attachment; filename="import_results.csv"'
            return resp
        except Exception, e:
            return HttpResponse(str(e), 'text/plain')


    return HttpResponse("""
<form method="post" action="" enctype="multipart/form-data">
  <div><input type="file" name="history" /></div>
  <div><button type="submit">Import historical stock reports</button></div>
</form>
""")
