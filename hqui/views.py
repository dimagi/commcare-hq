from django.shortcuts import render_to_response

def forms(req, template='hqui/forms.html'):
    return render_to_response(template, {})