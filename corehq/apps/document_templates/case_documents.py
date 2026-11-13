"""
Renders a batch of cases with their document templates into one PDF.

Each case picks its template with its ``document_template_slug`` property and
is rendered with its own properties as the template context.

Every case that cannot be rendered is reported as a :class:`Failure`, and
any failure fails the request.
"""
from casexml.apps.phone.data_providers.case.livequery import (
    get_live_case_ids_and_indices,
)
from attrs import define
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


@define(frozen=True)
class Failure:
    """A case that cannot be rendered

    :param name: the case name, or ``''`` if the case is not found or not accessible
    """
    case_id: str
    name: str
    reason: str


class CaseDocumentError(Exception):
    """The request cannot be rendered; the message and failures are safe to show to the user"""

    def __init__(self, message, failures=()):
        super().__init__(message)
        self.failures = list(failures)


def render_case_documents(domain, case_ids, couch_user):
    """Render each case with its template

    :param case_ids: IDs of cases in ``domain``
    :param couch_user: only cases this user has access to are rendered
    :returns: one PDF (bytes) with a document for each case, in the order of ``case_ids``
    :raises CaseDocumentError: if the request is invalid or any case fails.
        Its ``failures`` list each failed case in the order of ``case_ids``.
    """
    case_ids = list(dict.fromkeys(case_ids))
    if not case_ids:
        raise CaseDocumentError(_('No cases given'))
    if len(case_ids) > MAX_CASES:
        raise CaseDocumentError(_('At most {max} cases can be rendered at once').format(max=MAX_CASES))

    cases = _get_cases(domain, case_ids, couch_user)
    templates = _get_templates(domain, cases.values())
    documents = []
    failures = []
    for case_id in case_ids:
        case = cases.get(case_id)
        if case is None:
            failures.append(Failure(case_id, '', _('Case not found')))
            continue
        template = templates.get(case.get_case_property(SLUG_PROPERTY))
        if template is None:
            failures.append(Failure(case_id, case.name, _('No known "{property}"').format(property=SLUG_PROPERTY)))
            continue
        try:
            areas = load_images(domain, template.areas)
            documents.append(generate_document(areas, case.get_properties_in_api_format()))
        except (DocumentRenderError, ImageError) as error:
            failures.append(Failure(case_id, case.name, str(error)))

    if failures:
        raise CaseDocumentError(
            _('{count} of {total} cases cannot be rendered').format(count=len(failures), total=len(case_ids)),
            failures,
        )
    return render_pdf(documents)


def _get_cases(domain, case_ids, couch_user):
    """:returns: ``{case_id: case}`` of the cases the user can access; others are left out"""
    cases = CommCareCase.objects.get_cases(case_ids, ordered=True)
    accessible_ids = _get_live_case_ids(domain, couch_user)
    return {
        case.case_id: case for case in cases
        if case.domain == domain and not case.is_deleted and case.case_id in accessible_ids
    }


def _get_live_case_ids(domain, couch_user):
    owned_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
        domain, couch_user.get_owner_ids(domain), closed=False)
    live_ids, _indices = get_live_case_ids_and_indices(domain, owned_ids, TimingContext())
    return live_ids


def _get_templates(domain, cases):
    """:returns: ``{slug: template}`` of the live templates the cases use"""
    slugs = {case.get_case_property(SLUG_PROPERTY) for case in cases}
    live = Template.objects.filter(domain=domain, slug__in=slugs - {None, ''}, deleted=False)
    return {t.slug: t for t in live}
