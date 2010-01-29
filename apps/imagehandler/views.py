from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from rapidsms.webui.utils import render_to_response


@login_required()
def home(request, template_name="imagehandler/list.html"):
    return render_to_response(request, template_name, {})


# 
# def list(request, template_name="requestlogger/log_list.html"):
#     all_logs = RequestLog.objects.all()
#     return render_to_response(request, template_name, {"all_requests": all_logs})
