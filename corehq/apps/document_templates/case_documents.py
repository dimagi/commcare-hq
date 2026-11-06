"""
Renders a batch of cases with their document templates into one PDF.

Each case picks its template with its ``document_template_slug`` property and
is rendered with its own properties as the template context.
"""
from casexml.apps.phone.data_providers.case.livequery import (
    get_live_case_ids_and_indices,
)
from django.utils.translation import gettext as _

from corehq.apps.document_templates.images import ImageError, load_images
from corehq.apps.document_templates.models import Template
from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    generate_document,
    render_pdf,
)
from corehq.form_processor.models import CommCareCase
from corehq.util.timer import TimingContext

SLUG_PROPERTY = 'document_template_slug'
MAX_CASES = 50


class CaseDocumentError(Exception):
    """The request cannot be rendered; the message is safe to show to the user"""


def render_case_documents(domain, case_ids, couch_user):
    """Render each case with its template

    :param case_ids: IDs of cases in ``domain``
    :param couch_user: only cases this user has access to are rendered
    :returns: one PDF (bytes) with a document for each case, in the order of ``case_ids``
    :raises CaseDocumentError: if any case cannot be rendered, or the user
        has no access to it. Nothing is returned for the cases that could.
    """
    case_ids = list(dict.fromkeys(case_ids))
    if not case_ids:
        raise CaseDocumentError(_('No cases given'))
    if len(case_ids) > MAX_CASES:
        raise CaseDocumentError(_('At most {max} cases can be rendered at once').format(max=MAX_CASES))

    cases = _get_cases(domain, case_ids, couch_user)
    templates = _get_templates(domain, cases)
    documents = []
    for case in cases:
        try:
            areas = load_images(domain, templates[case.get_case_property(SLUG_PROPERTY)].areas)
            documents.append(generate_document(areas, case.get_properties_in_api_format()))
        except (DocumentRenderError, ImageError) as error:
            raise CaseDocumentError(_('Case {case_id}: {error}').format(case_id=case.case_id, error=error))
    return render_pdf(documents)


def _get_cases(domain, case_ids, couch_user):
    cases = CommCareCase.objects.get_cases(case_ids, ordered=True)
    cases = [case for case in cases if case.domain == domain and not case.is_deleted]
    accessible_ids = _get_live_case_ids(domain, couch_user)
    cases = [case for case in cases if case.case_id in accessible_ids]
    found = {case.case_id for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in found]
    if missing:
        raise CaseDocumentError(_('Cases not found: {ids}').format(ids=', '.join(missing)))
    return cases


def _get_live_case_ids(domain, couch_user):
    owned_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
        domain, couch_user.get_owner_ids(domain), closed=False)
    live_ids, _indices = get_live_case_ids_and_indices(domain, owned_ids, TimingContext())
    return live_ids


def _get_templates(domain, cases):
    slugs = {case.get_case_property(SLUG_PROPERTY) for case in cases}
    live = Template.objects.filter(domain=domain, slug__in=slugs - {None, ''}, deleted=False)
    templates = {t.slug: t for t in live}
    unknown = [case.case_id for case in cases if case.get_case_property(SLUG_PROPERTY) not in templates]
    if unknown:
        raise CaseDocumentError(
            _('Cases without a known "{property}": {ids}').format(property=SLUG_PROPERTY, ids=', '.join(unknown))
        )
    return templates
