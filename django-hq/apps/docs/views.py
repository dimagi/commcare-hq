#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from rapidsms.webui.utils import render_to_response

def index(request, topic, template_name="docs/index.html"):
    context = {}
    fin = open("apps/docs/static/" + topic + ".rst")
    context['content'] = fin.read()
    fin.close()
    return render_to_response(request, template_name, context)

