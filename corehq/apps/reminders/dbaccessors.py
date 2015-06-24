def get_surveys_in_domain(domain):
    from corehq.apps.reminders.models import Survey
    return sorted(Survey.view(
        'domain/docs',
        startkey=[domain, 'Survey'],
        endkey=[domain, 'Survey', {}],
        include_docs=True,
        reduce=False,
    ), key=lambda survey: survey.name)
