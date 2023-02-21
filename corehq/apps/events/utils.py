import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock
from corehq.form_processor.models import CommCareCaseIndex


def create_case_with_case_type(case_type, case_args, index=None):
    case_block = CaseBlock(
        case_id=uuid.uuid4().hex,
        case_type=case_type,
        case_name=case_args.get('name', None),
        domain=case_args['domain'],
        owner_id=case_args.get('owner_id', ''),
        update=case_args['properties'],
        create=True,
    )
    _, cases = submit_case_blocks(
        [case_block.as_text()],
        domain=case_args['domain'],
    )
    case_ = cases[0]

    if index is not None:
        case_.track_create(CommCareCaseIndex(
            case=case_,
            domain=case_.domain,
            referenced_id=index.get('parent_case_id'),
            relationship_id=CommCareCaseIndex.EXTENSION,
            referenced_type=case_.type,
            identifier=index.get('identifier', 'host'),
        ))
        case_.save(with_tracked_models=True)

    return case_


def case_index_event_identifier(event_id):
    return f'event-{event_id}'
