#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import os
from rapidsms.webui.utils import render_to_response

def index(request, topic, template_name="docs/index.html"):
    context = {}
    filedir = os.path.dirname(__file__)
    filepath = os.path.join( filedir,"content",topic + ".rst")
    fin = open(filepath)
    context['content'] = fin.read()
    fin.close()
    return render_to_response(request, template_name, context)

