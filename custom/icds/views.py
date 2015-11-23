from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string


def tableau(request):
    context = {
        'report_view': 'POCReports/MainDashboard'
    }
    response = render_to_string('tableau.html', context)
    return HttpResponse(response)
    # return render(request, context=context, template='tableau.html')
