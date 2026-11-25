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
    :returns: one PDF (bytes) with a document for each case ID, in the
        order of ``case_ids``. A repeated case ID gets a document each time.
    :raises CaseDocumentError: if any case cannot be rendered, or the user
        has no access to it. Nothing is returned for the cases that could.
    """
    if not case_ids:
        raise CaseDocumentError(_('No cases given'))
    if len(case_ids) > MAX_CASES:
        raise CaseDocumentError(_('At most {max} cases can be rendered at once').format(max=MAX_CASES))

    cases_by_id = _get_cases(domain, case_ids, couch_user)
    areas_by_slug = _load_areas(domain, _get_templates(domain, cases_by_id.values()))
    documents = []
    for case_id in case_ids:
        case = cases_by_id[case_id]
        try:
            documents.append(generate_document(
                areas_by_slug[case.get_case_property(SLUG_PROPERTY)],
                {**case.get_properties_in_api_format(), 'case_id': case_id},
            ))
        except DocumentRenderError as error:
            raise CaseDocumentError(_('Case {case_id}: {error}').format(case_id=case_id, error=error))
    return render_pdf(documents)


def _load_areas(domain, templates):
    """The areas of each template by slug, with the images loaded once for all the cases"""
    areas_by_slug = {}
    for slug, template in templates.items():
        try:
            areas_by_slug[slug] = load_images(domain, template.areas)
        except ImageError as error:
            raise CaseDocumentError(_('Template {slug}: {error}').format(slug=slug, error=error))
    return areas_by_slug


def _get_cases(domain, case_ids, couch_user):
    unique_ids = list(dict.fromkeys(case_ids))
    accessible_ids = _get_live_case_ids(domain, couch_user)
    cases_by_id = {
        case.case_id: case
        for case in CommCareCase.objects.get_cases(unique_ids)
        if case.domain == domain and not case.is_deleted and case.case_id in accessible_ids
    }
    missing = [case_id for case_id in unique_ids if case_id not in cases_by_id]
    if missing:
        raise CaseDocumentError(_('Cases not found: {ids}').format(ids=', '.join(missing)))
    return cases_by_id


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
