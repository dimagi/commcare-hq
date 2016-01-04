from datetime import datetime
from corehq.apps.domain.decorators import require_superuser
from django.http import HttpResponse

from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.tasks import process_repeater_list

PAGE = """
<html>
<body>
    <p>Forward forms and cases for %(domain)s</p>
    <form action="" method="post">
        <input type="submit" value="Go"/>
    </form>
    <p>%(status)s</p>
</body>
</html>
"""


@require_superuser
def check_repeaters(request, domain):
    if request.method == 'GET':
        return HttpResponse(PAGE % {'status': '', 'domain': domain})
    elif request.method == 'POST':
        start = datetime.utcnow()
        repeat_records = RepeatRecord.all(domain, due_before=start, limit=100)
        process_repeater_list(repeat_records)
        return HttpResponse(PAGE % {'status': 'Done', 'domain': domain})
