#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from corehq.util.webutils import render_to_response

def messaging(request, domain, template="sms/default.html"):
    return render_to_response(request, template, {
        'domain': domain,
    })

def user_messaging(request, domain, template="sms/user_messaging.html"):
    return render_to_response(request, template, {
        'domain': domain,
    })

def group_messaging(request, domain, template="sms/group_messaging.html"):
    return render_to_response(request, template, {
        'domain': domain,
    })

