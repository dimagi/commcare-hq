from django.http import Http404
from corehq.util.webutils import render_to_response

def users(req, domain, template="users/users.html"):
    return render_to_response(req, template, {
        'domain': domain,
    })