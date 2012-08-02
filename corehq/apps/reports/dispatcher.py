from django.http import HttpResponseNotFound, Http404
from dimagi.utils.modules import to_function


class ReportDispatcher(object):
    """
    This is sorta like a poor man's class based view. Added so that multiple
    modules can easily leverage the reports framework in their views.
    """
    
    def __init__(self, mapping, permissions_check):
        """
        mapping should be formatted like:
        
        STANDARD_REPORT_MAP = {
            "Monitor Workers" : [
                'corehq.apps.reports.standard.CaseActivityReport',
                'corehq.apps.reports.standard.SubmissionsByFormReport',
            ],
            "Inspect Data" : [
                'corehq.apps.reports.standard.SubmitHistory',
                'corehq.apps.reports.standard.MapReport',
            ],
        }
        
        permissions_check should be a function that takes in a couch_user,
        domain, and a report model, and returns true if the user is allowed to 
        view that report / use that model.

        """
        self.mapping = mapping
        self.permissions_check = permissions_check
        
    def dispatch(self, request, domain, slug, return_json=False, export=False,
                 custom=False, async=False, async_filters=False, 
                 static_only=False):
        """
        Dispatch a report. Returns a 404 if permisisons checks fail or the 
        report is not found. Otherwise returns an HTTP response from the 
        matching report object.
        """
        if not self.mapping or (custom and not domain in self.mapping):
            return HttpResponseNotFound("Sorry, no reports have been configured yet.")
        
        mapping = self.mapping[domain] if custom else self.mapping
        for key, models in mapping.items():
            for model in models:
                klass = to_function(model)
                if klass.slug == slug:
                    k = klass(domain, request)
                    if not self.permissions_check(request.couch_user, 
                                                  domain, model):
                        raise Http404
                    elif return_json:
                        return k.as_json()
                    elif export:
                        return k.as_export()
                    elif async:
                        return k.as_async(static_only=static_only)
                    elif async_filters:
                        return k.as_async_filters()
                    else:
                        return k.as_view()
        raise Http404