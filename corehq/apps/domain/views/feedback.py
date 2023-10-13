import json

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_POST

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.tasks import send_mail_async


@login_and_domain_required
@require_POST
def submit_feedback(request, domain):
    rating = {
        '1': "Don't Like It / Not Useful",
        '2': "Not Sure / Confusing",
        '3': "Love It / Useful",
    }[request.POST.get('rating')]
    additional_feedback = request.POST.get('additionalFeedback')
    feature_name = request.POST.get('featureName')
    message = '\n'.join([
        '{user} left feedback for "{feature}" on {domain}.',
        '',
        'Rating: {rating}',
        '',
        'Additional Feedback:',
        '{additional_feedback}',
    ]).format(
        user=request.couch_user.username,
        domain=domain,
        feature=feature_name,
        rating=rating,
        additional_feedback=additional_feedback,
    )
    send_mail_async.delay(
        '{} Feedback Received'.format(feature_name),
        message,
        [settings.FEEDBACK_EMAIL],
    )
    return HttpResponse(json.dumps({
        'success': True,
    }), content_type="application/json")
