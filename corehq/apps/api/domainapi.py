from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import View
from corehq.apps.domain.decorators import login_and_domain_required

class DomainAPI(View):
    """
    DomainAPI allows for additional separate RESTful assets to be accessible within or outside
    the context of the reports UI.

    URL addition is added via inspecting subclasses of this parent class and appending
    the name and version of the domain of this API instance in question.
    """

    #If enabling CSRF, here's how to access it over APIs
    #note - for security purposes, csrf protection is ENABLED
    #query={query_json}
    #csrfmiddlewaretoken=token

    #in curl, this is:
    #curl -b "csrftoken=<csrftoken>;sessionid=<session_id>" -H "Content-Type: application/json" -XPOST http://server/a/domain/api/v0.1/xform_es/
    #     -d"query=@myquery.json&csrfmiddlewaretoken=<csrftoken>"

    @classmethod
    def allowed_domain(self, domain):
        return False

    @classmethod
    def api_version(cls):
        raise NotImplementedError("This API's version is not implemented")

    @classmethod
    def api_name(cls):
        raise NotImplementedError("This API's name is not implemented")

    http_method_names = ['get', 'post', 'head', ]
    def get(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")
    def post(self,  *args, **kwargs):
        raise NotImplementedError("Not implemented")
    def head(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        req = args[0]
        if not self.allowed_domain(req.domain):
            raise Http404
        ret =  super(DomainAPI, self).dispatch(*args, **kwargs)
        return ret
