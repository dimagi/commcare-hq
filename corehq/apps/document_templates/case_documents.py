"""
Renders a batch of cases with their document templates.

Each case picks its template with its ``document_template_slug`` property and
is rendered with its own properties as the template context.
"""
from django.utils.translation import gettext as _

from corehq.apps.document_templates.models import Template
from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    render_template,
)
from corehq.form_processor.models import CommCareCase

SLUG_PROPERTY = 'document_template_slug'
MAX_CASES = 50


class CaseDocumentError(Exception):
    """The request cannot be rendered; the message is safe to show to the user"""


def render_case_documents(domain, case_ids):
    """Render each case with its template

    :param case_ids: IDs of cases in ``domain``
    :returns: HTML documents, in the order of ``case_ids``
    :raises CaseDocumentError: if any case cannot be rendered. Nothing is
        returned for the cases that could.
    """
    case_ids = list(dict.fromkeys(case_ids))
    if not case_ids:
        raise CaseDocumentError(_('No cases given'))
    if len(case_ids) > MAX_CASES:
        raise CaseDocumentError(_('At most {max} cases can be rendered at once').format(max=MAX_CASES))

    cases = _get_cases(domain, case_ids)
    templates = _get_templates(domain, cases)
    documents = []
    for case in cases:
        try:
            documents.append(render_template(templates[case.get_case_property(SLUG_PROPERTY)],
                                             case.get_properties_in_api_format()))
        except DocumentRenderError as error:
            raise CaseDocumentError(_('Case {case_id}: {error}').format(case_id=case.case_id, error=error))
    return documents


def _get_cases(domain, case_ids):
    cases = CommCareCase.objects.get_cases(case_ids, ordered=True)
    # get_cases is not scoped to a domain
    cases = [case for case in cases if case.domain == domain and not case.is_deleted]
    found = {case.case_id for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in found]
    if missing:
        raise CaseDocumentError(_('Cases not found: {ids}').format(ids=', '.join(missing)))
    return cases


def _get_templates(domain, cases):
    slugs = {case.get_case_property(SLUG_PROPERTY) for case in cases}
    templates = {t.slug: t for t in Template.objects.filter(domain=domain, slug__in=slugs - {None, ''})}
    unknown = [case.case_id for case in cases if case.get_case_property(SLUG_PROPERTY) not in templates]
    if unknown:
        raise CaseDocumentError(
            _('Cases without a known "{property}": {ids}').format(property=SLUG_PROPERTY, ids=', '.join(unknown))
        )
    return templates
