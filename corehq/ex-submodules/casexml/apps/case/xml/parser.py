"""
This isn't really a parser, but it's the code that generates case-like
objects from things from xforms.
"""
import datetime

from casexml.apps.case import const
from casexml.apps.case.xml import DEFAULT_VERSION, V1, V2, NS_REVERSE_LOOKUP_MAP
from dimagi.utils.logging import notify_error
from dimagi.utils.parsing import string_to_utc_datetime

from corehq.util.global_request import get_request_domain
from corehq.util.metrics import metrics_counter

XMLNS_ATTR = "@xmlns"
KNOWN_PROPERTIES = {
    'name': '',
    'external_id': '',
    'type': '',
    'owner_id': '',
    'opened_on': None,
    'user_id': '',
}


def get_version(case_block):
    """
    Given a case block, determine what version it is.
    """
    xmlns = case_block.get(XMLNS_ATTR, "")
    if xmlns:
        if xmlns not in NS_REVERSE_LOOKUP_MAP:
            raise CaseGenerationException(
                "%s not a valid case xmlns. "
                "We don't know how to handle this version." % xmlns
            )
        return NS_REVERSE_LOOKUP_MAP[xmlns]
    domain = get_request_domain()
    tags = {"domain": domain} if domain else {}
    metrics_counter("commcare.deprecated.v1caseblock", tags=tags)
    notify_error("encountered deprecated V1 case block")
    return DEFAULT_VERSION


class CaseGenerationException(Exception):
    """
    When anything illegal/unexpected happens while working with case parsing
    """
    pass


def case_update_from_block(case_block):
    case_version = get_version(case_block)
    return VERSION_FUNCTION_MAP[case_version](case_block)


def case_id_from_block(case_block):
    return CASE_ID_FUNCTION_MAP[get_version(case_block)](case_block)


class CaseActionBase(object):
    action_type_slug = None

    def __init__(self, block, type=None, name=None, external_id=None,
                 user_id=None, owner_id=None, opened_on=None,
                 dynamic_properties=None, indices=None, attachments=None):
        self.raw_block = block
        self.type = type
        self.name = name
        self.external_id = external_id
        self.user_id = user_id
        self.owner_id = owner_id
        self.opened_on = opened_on
        self.dynamic_properties = dynamic_properties or {}
        self.indices = indices or []
        self.attachments = attachments or {}

    def get_known_properties(self):
        return dict((p, getattr(self, p)) for p in KNOWN_PROPERTIES.keys()
                    if getattr(self, p) is not None)

    def __repr__(self):
        return f"{type(self).__name__}(block={self.raw_block!r})"

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def _from_block_and_mapping(cls, block, mapping):
        def _normalize(val):
            if isinstance(val, list):
                # if we get multiple updates, they look like a list.
                # normalize these by taking the last item
                return val[-1]
            return val

        kwargs = {}
        dynamic_properties = {}
        # if not a dict, it's probably an empty close block
        if isinstance(block, dict):
            for k, v in block.items():
                if k in mapping:
                    kwargs[mapping[k]] = v
                else:
                    dynamic_properties[k] = _normalize(v)

        return cls(block, dynamic_properties=dynamic_properties,
                   **kwargs)

    @classmethod
    def from_v1(cls, block):
        return cls._from_block_and_mapping(block, cls.V1_PROPERTY_MAPPING)

    @classmethod
    def from_v2(cls, block):
        return cls._from_block_and_mapping(block, cls.V2_PROPERTY_MAPPING)

    V1_PROPERTY_MAPPING = {
        const.CASE_TAG_TYPE_ID: "type",
        const.CASE_TAG_NAME: "name",
        const.CASE_TAG_EXTERNAL_ID: "external_id",
        const.CASE_TAG_USER_ID: "user_id",
        const.CASE_TAG_OWNER_ID: "owner_id",
        const.CASE_TAG_DATE_OPENED: "opened_on"
    }

    # the only difference is the place where "type" is stored
    V2_PROPERTY_MAPPING = {
        const.CASE_TAG_TYPE: "type",
        const.CASE_TAG_NAME: "name",
        const.CASE_TAG_EXTERNAL_ID: "external_id",
        const.CASE_TAG_USER_ID: "user_id",
        const.CASE_TAG_OWNER_ID: "owner_id",
        const.CASE_TAG_DATE_OPENED: "opened_on"
    }


class CaseNoopAction(CaseActionBase):
    """
    Form completed against case without updating any properties (empty case block)
    """
    action_type_slug = const.CASE_ACTION_UPDATE

    def get_known_properties(self):
        return {}


class CaseCreateAction(CaseActionBase):
    action_type_slug = const.CASE_ACTION_CREATE


class CaseUpdateAction(CaseActionBase):
    action_type_slug = const.CASE_ACTION_UPDATE


class CaseCloseAction(CaseActionBase):
    action_type_slug = const.CASE_ACTION_CLOSE


class AbstractAction(object):

    def __init__(self, action_type_slug):
        self.action_type_slug = action_type_slug

        self.dynamic_properties = {}
        self.indices = []
        self.attachments = {}
        # TODO log which products were touched?

    def get_known_properties(self):
        return {}


class CaseAttachment(object):
    """
    A class that wraps an attachment to a case
    """

    def __init__(self, identifier, attachment_src, attachment_from, attachment_name):
        """
        identifier: the tag name
        attachment_src: URL of attachment
        attachment_from: source [local, remote, inline]
        attachment_name: required if inline for inline blob of attachment -
        likely identical to identifier
        """
        self.identifier = identifier
        self.attachment_src = attachment_src
        self.attachment_from = attachment_from
        self.attachment_name = attachment_name

    @property
    def is_delete(self):
        """
        Helper method to see if this is a delete vs. update

        The spec says "no attributes, empty - This will remove the attachment."
        This implementation only considers `src` and `from` values since that
        should be sufficient to detect a deletion. However, technically the
        `name` value could be considered as well, although having a non-empty
        `name` with empty `src` and `from` is an undefined state.
        https://github.com/dimagi/commcare-core/wiki/casexml20#case-action-elements
        """
        return not (self.attachment_src or self.attachment_from)


class CaseAttachmentAction(CaseActionBase):
    action_type_slug = const.CASE_ACTION_ATTACHMENT

    def __init__(self, block, attachments):
        super(CaseAttachmentAction, self).__init__(block, attachments=attachments)

    @classmethod
    def from_v1(cls, block):
        # indices are not supported in v1
        return cls(block, [])

    @classmethod
    def from_v2(cls, block):
        attachments = {}
        if not isinstance(block, dict):
            return cls(block, attachments)

        for id, data in block.items():
            if isinstance(data, str):
                attachment_src = None
                attachment_from = None
                attachment_name = None
            else:
                attachment_src = data.get('@src', None)
                attachment_from = data.get('@from', None)
                attachment_name = data.get('@name', None)
            attachments[id] = CaseAttachment(id, attachment_src, attachment_from, attachment_name)
        return cls(block, attachments)


class CaseIndex(object):
    """
    A class that holds an index to a case.
    """

    def __init__(self, identifier, referenced_type, referenced_id, relationship=None):
        self.identifier = identifier
        self.referenced_type = referenced_type
        self.referenced_id = referenced_id
        self.relationship = relationship or "child"


class CaseIndexAction(CaseActionBase):
    """
    Action describing updates to the case indices
    """
    action_type_slug = const.CASE_ACTION_INDEX

    def __init__(self, block, indices):
        super(CaseIndexAction, self).__init__(block, indices=indices)

    def get_known_properties(self):
        # override this since the index action only cares about a list of indices
        return {}

    @classmethod
    def from_v1(cls, block):
        # indices are not supported in v1
        return cls(block, [])

    @classmethod
    def from_v2(cls, block):
        indices = []
        if not isinstance(block, dict):
            return cls(block, indices)

        for id, data in block.items():
            if "@case_type" not in data:
                raise CaseGenerationException("Invalid index, must have a case type attribute.")
            indices.append(CaseIndex(id, data["@case_type"], data.get("#text", ""),
                                     data.get("@relationship", 'child')))
        return cls(block, indices)


class CaseUpdate(object):
    """
    A temporary model that parses the data from the form consistently.
    The actual Case objects use this to update themselves.
    """

    def __init__(self, id, version, block, user_id="", modified_on_str=""):
        self.id = id
        self.version = version
        self.user_id = user_id
        self.modified_on_str = modified_on_str

        # deal with the various blocks
        self.raw_block = block
        self.create_block = block.get(const.CASE_ACTION_CREATE, {})
        self.update_block = block.get(const.CASE_ACTION_UPDATE, {})
        self.close_block = block.get(const.CASE_ACTION_CLOSE, {})
        self._closes_case = const.CASE_ACTION_CLOSE in block
        self.index_block = block.get(const.CASE_ACTION_INDEX, {})
        self.attachment_block = block.get(const.CASE_ACTION_ATTACHMENT, {})

        # referrals? really? really???
        self.referral_block = block.get(const.REFERRAL_TAG, {})

        # actions
        self.actions = []
        if self.creates_case():
            self.actions.append(CREATE_ACTION_FUNCTION_MAP[self.version](self.create_block))
        if self.updates_case():
            self.actions.append(UPDATE_ACTION_FUNCTION_MAP[self.version](self.update_block))
        if self.closes_case():
            self.actions.append(CLOSE_ACTION_FUNCTION_MAP[self.version](self.close_block))
        if self.has_indices():
            self.actions.append(INDEX_ACTION_FUNCTION_MAP[self.version](self.index_block))
        if self.has_attachments():
            self.actions.append(ATTACHMENT_ACTION_FUNCTION_MAP[self.version](self.attachment_block))

        if not self.actions:
            self.actions.append(NOOP_ACTION_FUNCTION_MAP[self.version]({}))

    def guess_modified_on(self):
        """
        Guess the modified date, defaulting to the current time in UTC.
        """
        return string_to_utc_datetime(self.modified_on_str) if self.modified_on_str else datetime.datetime.utcnow()

    def creates_case(self):
        # creates have to have actual data in them so this is fine
        return bool(self.create_block)

    def updates_case(self):
        # updates have to have actual data in them so this is fine
        return bool(self.update_block)

    def closes_case(self):
        # closes might not have data and so we store this separately
        return self._closes_case

    def has_indices(self):
        return bool(self.index_block)

    def has_referrals(self):
        return bool(self.referral_block)

    def has_attachments(self):
        return bool(self.attachment_block)

    def __str__(self):
        return "%s: %s" % (self.version, self.id)

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)

    def _filtered_action(self, func):
        # filters the actions, assumes exactly 0 or 1 match.
        filtered = list(filter(func, self.actions))
        if filtered:
            assert len(filtered) == 1
            return filtered[0]

    def get_create_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseCreateAction))

    def get_update_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseUpdateAction))

    def get_close_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseCloseAction))

    def get_index_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseIndexAction))

    def get_attachment_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseAttachmentAction))

    def get_normalized_update_property_names(self):
        changed_properties = set()
        if self.creates_case():
            changed_properties.update(self.get_create_action().raw_block.keys())
        if self.updates_case():
            changed_properties.update(self.get_update_action().raw_block.keys())

        property_map = \
            CaseCreateAction.V1_PROPERTY_MAPPING if self.version == V1 else CaseCreateAction.V2_PROPERTY_MAPPING

        normalized_properties = {property_map.get(prop, prop) for prop in changed_properties}
        return normalized_properties

    @classmethod
    def from_v1(cls, case_block):
        """
        Gets a case update from a version 1 case.
        Spec: https://bitbucket.org/javarosa/javarosa/wiki/casexml
        """
        case_id = cls.v1_case_id_from(case_block)
        modified_on = case_block.get(const.CASE_TAG_MODIFIED, "")
        return cls(id=case_id, version=V1, block=case_block, modified_on_str=modified_on)

    @classmethod
    def from_v2(cls, case_block):
        """
        Gets a case update from a version 2 case.
        Spec: https://github.com/dimagi/commcare/wiki/casexml20
        """
        return cls(id=cls.v2_case_id_from(case_block),
                   version=V2,
                   block=case_block,
                   user_id=case_block.get(_USER_ID_ATTR, ""),
                   modified_on_str=case_block.get(_MODIFIED_ATTR, ""))

    @classmethod
    def v1_case_id_from(cls, case_block):
        try:
            return case_block[const.CASE_TAG_ID]
        except KeyError:
            raise CaseGenerationException(
                "No case_id element found in v1 case block, "
                "this is a required property."
            )

    @classmethod
    def v2_case_id_from(cls, case_block):
        try:
            return case_block[_CASE_ID_ATTR]
        except KeyError:
            raise CaseGenerationException(
                "No case_id attribute found in v2 case block, "
                "this is a required property."
            )


_CASE_ID_ATTR = "@" + const.CASE_TAG_ID
_USER_ID_ATTR = "@" + const.CASE_TAG_USER_ID
_MODIFIED_ATTR = "@" + const.CASE_TAG_MODIFIED


# this section is what maps various things to their v1/v2 parsers
VERSION_FUNCTION_MAP = {
    V1: CaseUpdate.from_v1,
    V2: CaseUpdate.from_v2
}

CASE_ID_FUNCTION_MAP = {
    V1: CaseUpdate.v1_case_id_from,
    V2: CaseUpdate.v2_case_id_from
}

NOOP_ACTION_FUNCTION_MAP = {
    V1: CaseNoopAction.from_v1,
    V2: CaseNoopAction.from_v2
}

CREATE_ACTION_FUNCTION_MAP = {
    V1: CaseCreateAction.from_v1,
    V2: CaseCreateAction.from_v2
}

UPDATE_ACTION_FUNCTION_MAP = {
    V1: CaseUpdateAction.from_v1,
    V2: CaseUpdateAction.from_v2,
}

CLOSE_ACTION_FUNCTION_MAP = {
    V1: CaseCloseAction.from_v1,
    V2: CaseCloseAction.from_v2,
}
INDEX_ACTION_FUNCTION_MAP = {
    V1: CaseIndexAction.from_v1,
    V2: CaseIndexAction.from_v2
}

ATTACHMENT_ACTION_FUNCTION_MAP = {
    V1: CaseAttachmentAction.from_v1,
    V2: CaseAttachmentAction.from_v2
}
