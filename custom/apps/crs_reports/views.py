from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from django.shortcuts import render
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.reports.dispatcher import QuestionTemplateDispatcher
from corehq.apps.reports.views import require_case_view_permission
from casexml.apps.case.templatetags.case_tags import case_inline_display
from corehq.apps.app_manager.models import get_app
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
import re
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse
# import weasyprint


@require_case_view_permission
@login_and_domain_required
@require_GET
def crs_details_report(request, domain, case_id, report_slug):
    return render(request, "crs_reports/base_template.html", get_dict_to_report(domain, case_id, report_slug))


@require_case_view_permission
@login_and_domain_required
@require_GET
def render_to_pdf(request, domain, case_id, report_slug):
    if report_slug == "hbnc_mother_report":
        template = get_template("crs_reports/partials/mothers_form_reports_template.html")
    else:
        template = get_template("crs_reports/partials/baby_form_reports_template.html")

    context_dict = get_dict_to_report(domain, case_id, report_slug)
    context = Context(context_dict)
    html = template.render(context)
    response = HttpResponse(mimetype="application/pdf")
    # weasyprint.HTML(string=html).write_pdf(response)
    return response


def get_questions_with_answers(forms, domain, report_slug):
    questions = QuestionTemplateDispatcher().get_question_templates(domain, report_slug)
    for question in questions:
        question['answers'] = []
    for form in forms:
        form_dict = form.get_form
        for question in questions:
            if question['case_property'] in form_dict:
                question['answers'].append(form_dict[question['case_property']])
    for question in questions:
        if 'answers' not in question:
                question['answers'] = []
        if len(question['answers']) < 7:
            for i in range(len(question['answers']), 7):
                question['answers'].append('')
    return questions


def get_dict_to_report(domain, case_id, report_slug):
    try:
        case = CommCareCase.get(case_id)
    except ResourceNotFound:
        case = None

    try:
        owner_name = CommCareUser.get_by_user_id(case.owner_id, domain).full_name
    except Exception:
        owner_name = None

    try:
        owning_group = Group.get(case.owner_id)
        sub_center = owning_group.display_name if owning_group.domain == domain else ''
    except Exception:
        sub_center = None

    try:
        user = CommCareUser.get_by_user_id(case.user_id, domain)
    except Exception:
        user = None

    questions = get_questions_with_answers(case.get_forms(), domain, report_slug)

    return {
        "domain": domain,
        "case_id": case_id,
        "report": dict(
            name=case_inline_display(case),
            slug=report_slug,
            is_async=False,
        ),
        "owner_name": owner_name,
        "user": user,
        "sub_center": sub_center,
        "case": case,
        "questions": questions
    }
