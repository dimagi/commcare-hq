from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from rapidsms.webui.utils import render_to_response

from requestlogger.decorators import log_request                   
from requestlogger.models import RequestLog


@login_required()
@log_request()
def demo(request):
    return HttpResponse("Thanks!  Your request was logged.")

def list(request, template_name="requestlogger/log_list.html"):
    all_logs = RequestLog.objects.all()
    return render_to_response(request, template_name, {"all_requests": all_logs})
    
    
