from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from django.shortcuts import render
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.dispatcher import QuestionTemplateDispatcher
from corehq.apps.reports.views import require_case_view_permission
from casexml.apps.case.templatetags.case_tags import case_inline_display
from corehq.apps.users.models import CommCareUser
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse
# import weasyprint
from custom.apps.crs_reports import MOTHER_POSTPARTUM_VISIT_FORM_XMLNS, BABY_POSTPARTUM_VISIT_FORM_XMLNS


@require_case_view_permission
@login_and_domain_required
@require_GET
def crs_details_report(request, domain, case_id, report_slug):
    return render(request, "crs_reports/base_template.html", get_dict_to_report(domain, case_id, report_slug))


@require_case_view_permission
@login_and_domain_required
@require_GET
def render_to_pdf(request, domain, case_id, report_slug):
    template = get_template("crs_reports/partials/mothers_form_reports_template.html")

    context_dict = get_dict_to_report(domain, case_id, report_slug)
    context = Context(context_dict)
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    # weasyprint.HTML(string=html).write_pdf(response)
    return response


def get_questions_with_answers(forms, domain, report_slug):
    sections = QuestionTemplateDispatcher().get_question_templates(domain, report_slug)
    for section in sections:
        count = 7
        if section['questions'][0]['case_property'] == 'section_d':
            count = 8
        for question in section['questions']:
            question['answers'] = []
        for form in forms:
            form_dict = form.form
            for question in section['questions']:
                if form.xmlns == BABY_POSTPARTUM_VISIT_FORM_XMLNS and question['case_property'] in form_dict['baby_alive_group']:
                    question['answers'].append(form_dict['baby_alive_group'][question['case_property']])
                    continue

                if question['case_property'] in form_dict:
                    question['answers'].append(form_dict[question['case_property']])
        for question in section['questions']:

            if 'answers' not in question:
                    question['answers'] = []
            if len(question['answers']) < count:
                for i in range(len(question['answers']), count):
                    question['answers'].append('')
    return sections


def get_dict_to_report(domain, case_id, report_slug):
    try:
        case = CommCareCase.get(case_id)
    except ResourceNotFound:
        case = None

    baby_case = [c for c in case.get_subcases().all() if c.type == 'baby']
    if baby_case:
        mother_forms = [form for form in case.get_forms() if form.xmlns == MOTHER_POSTPARTUM_VISIT_FORM_XMLNS]
        baby_forms = [form for form in baby_case[0].get_forms() if form.xmlns == BABY_POSTPARTUM_VISIT_FORM_XMLNS]
        forms = mother_forms + baby_forms
    else:
        forms = [form for form in case.get_forms() if form.xmlns == MOTHER_POSTPARTUM_VISIT_FORM_XMLNS]

    try:
        user = CommCareUser.get_by_user_id(case.user_id, domain)
    except Exception:
        user = None

    sections = get_questions_with_answers(forms, domain, report_slug)

    return {
        "domain": domain,
        "case_id": case_id,
        "report": dict(
            name=case_inline_display(case),
            slug=report_slug,
            is_async=False,
        ),
        "user": user,
        "case": case,
        "sections": sections
    }
