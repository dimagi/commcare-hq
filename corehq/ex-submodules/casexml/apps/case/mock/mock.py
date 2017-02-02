from __future__ import absolute_import
import copy
import uuid

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS, CASE_INDEX_CHILD


class CaseStructure(object):
    """
    A structure representing a case and its related cases.

    Can recursively nest parents/grandparents inside here.
    """

    def __init__(self, case_id=None, indices=None, attrs=None, walk_related=True):
        self.case_id = case_id or uuid.uuid4().hex
        self.indices = indices if indices is not None else []
        self.attrs = attrs if attrs is not None else {}
        self.walk_related = walk_related  # whether to walk related cases in operations

    @property
    def index(self):
        return {
            r.identifier: (r.related_type, r.related_id, r.relationship)
            for r in self.indices
        }

    def walk_ids(self):
        yield self.case_id
        if self.walk_related:
            for relationship in self.indices:
                for id in relationship.related_structure.walk_ids():
                    yield id


class CaseIndex(object):
    DEFAULT_RELATIONSHIP = CASE_INDEX_CHILD
    DEFAULT_RELATED_CASE_TYPE = 'default_related_case_type'

    def __init__(self, related_structure=None, relationship=DEFAULT_RELATIONSHIP, related_type=None,
                 identifier=None):
        self.related_structure = related_structure or CaseStructure()
        self.relationship = relationship
        if related_type is None:
            related_type = self.related_structure.attrs.get('case_type', self.DEFAULT_RELATED_CASE_TYPE)
        self.related_type = related_type

        if identifier is None:
            self.identifier = DEFAULT_CASE_INDEX_IDENTIFIERS[relationship]
        else:
            self.identifier = identifier

    @property
    def related_id(self):
        return self.related_structure.case_id


class CaseFactory(object):
    """
    A case factory makes and updates cases for you using CaseStructures.

    The API is a wrapper around the CaseBlock utility and is designed to be
    easier to work with to setup parent/child structures or default properties.
    """

    def __init__(self, domain=None, case_defaults=None, form_extras=None):
        self.domain = domain
        self.case_defaults = case_defaults if case_defaults is not None else {}
        self.form_extras = form_extras if form_extras is not None else {}

    def get_case_block(self, case_id, **kwargs):
        for k, v in self.case_defaults.items():
            if k not in kwargs:
                kwargs[k] = v
        return CaseBlock(
            case_id=case_id,
            **kwargs
        ).as_xml()

    def post_case_blocks(self, caseblocks, form_extras=None):
        submit_form_extras = copy.copy(self.form_extras)
        if form_extras is not None:
            submit_form_extras.update(form_extras)
        return post_case_blocks(
            caseblocks,
            form_extras=submit_form_extras,
            domain=self.domain,
        )

    def create_case(self, **kwargs):
        """
        Shortcut to create a simple case without needing to make a structure for it.
        """
        kwargs['create'] = True
        return self.create_or_update_case(CaseStructure(case_id=uuid.uuid4().hex, attrs=kwargs))[0]

    def update_case(self, case_id, **kwargs):
        """
        Shortcut to update a simple case given its id without needing to make a structure for it.
        """
        kwargs['create'] = False
        return self.create_or_update_case(CaseStructure(case_id=case_id, attrs=kwargs))[0]

    def close_case(self, case_id):
        """
        Shortcut to close a case (and do nothing else)
        """
        return self.create_or_update_case(CaseStructure(case_id=case_id, attrs={'close': True}))[0]

    def create_or_update_case(self, case_structure, form_extras=None):
        return self.create_or_update_cases([case_structure], form_extras)

    def create_or_update_cases(self, case_structures, form_extras=None):
        from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

        def _get_case_block(substructure):
            return self.get_case_block(substructure.case_id, index=substructure.index, **substructure.attrs)

        def _get_case_blocks(substructure):
            blocks = [_get_case_block(substructure)]
            if substructure.walk_related:
                blocks += [
                    block for relationship in substructure.indices
                    for block in _get_case_blocks(relationship.related_structure)
                ]
            return blocks

        self.post_case_blocks(
            [block for structure in case_structures for block in _get_case_blocks(structure)],
            form_extras,
        )

        case_ids = [id for structure in case_structures for id in structure.walk_ids()]
        return list(CaseAccessors(self.domain).get_cases(case_ids, ordered=True))
