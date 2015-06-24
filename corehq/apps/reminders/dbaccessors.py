def get_surveys_in_domain(domain):
    from corehq.apps.reminders.models import Survey
    return Survey.view(
        'reminders/survey_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True
    ).all()
