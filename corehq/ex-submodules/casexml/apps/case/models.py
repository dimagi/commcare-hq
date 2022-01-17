"""
Couch models for commcare cases.

For details on casexml check out:
http://bitbucket.org/javarosa/javarosa/wiki/casexml
"""
from django.core.cache import cache

from dimagi.ext.couchdbkit import *  # noqa: F403
from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex, CommCareCaseAttachment
from dimagi.utils.couch import LooselyEqualDocumentSchema

INDEX_RELATIONSHIP_CHILD = 'child'
INDEX_RELATIONSHIP_EXTENSION = 'extension'


class CommCareCaseAction(LooselyEqualDocumentSchema):
    """
    An atomic action on a case. Either a create, update, or close block in
    the xml.
    """
    action_type = StringProperty(choices=list(const.CASE_ACTIONS))
    user_id = StringProperty()
    date = DateTimeProperty()
    server_date = DateTimeProperty()
    xform_id = StringProperty()
    xform_xmlns = StringProperty()
    xform_name = StringProperty()
    sync_log_id = StringProperty()

    updated_known_properties = DictProperty()
    updated_unknown_properties = DictProperty()
    indices = SchemaListProperty(CommCareCaseIndex)
    attachments = SchemaDictProperty(CommCareCaseAttachment)

    deprecated = False

    @classmethod
    def from_parsed_action(cls, date, user_id, xformdoc, action):
        if not action.action_type_slug in const.CASE_ACTIONS:
            raise ValueError("%s not a valid case action!" % action.action_type_slug)

        user_id = user_id or xformdoc.user_id
        ret = CommCareCaseAction(action_type=action.action_type_slug, date=date, user_id=user_id)

        ret.server_date = xformdoc.received_on
        ret.xform_id = xformdoc.form_id
        ret.xform_xmlns = xformdoc.xmlns
        ret.xform_name = getattr(xformdoc, 'name', '')
        ret.updated_known_properties = action.get_known_properties()

        ret.updated_unknown_properties = action.dynamic_properties
        ret.indices = [CommCareCaseIndex.from_case_index_update(i) for i in action.indices]
        ret.attachments = dict((attach_id, CommCareCaseAttachment.from_case_index_update(attach))
                               for attach_id, attach in action.attachments.items())
        if hasattr(xformdoc, "last_sync_token"):
            ret.sync_log_id = xformdoc.last_sync_token
        return ret

    @property
    def xform(self):
        raise NotImplementedError

    @property
    def form(self):
        """For compatability with CaseTransaction"""
        return self.xform

    @property
    def form_id(self):
        """For compatability with CaseTransaction"""
        return self.xform_id

    @property
    def is_case_create(self):
        return self.action_type == const.CASE_ACTION_CREATE

    @property
    def is_case_close(self):
        return self.action_type == const.CASE_ACTION_CLOSE

    @property
    def is_case_index(self):
        return self.action_type == const.CASE_ACTION_INDEX

    @property
    def is_case_attachment(self):
        return self.action_type == const.CASE_ACTION_ATTACHMENT

    @property
    def is_case_rebuild(self):
        return self.action_type == const.CASE_ACTION_REBUILD

    def get_user_id(self):
        key = 'xform-%s-user_id' % self.xform_id
        id = cache.get(key)
        if not id:
            xform = self.xform
            try:
                id = xform.metadata.userID
            except AttributeError:
                id = None
            cache.set(key, id, 12*60*60)
        return id

    def __repr__(self):
        return "{xform}: {type} - {date} ({server_date})".format(
            xform=self.xform_id, type=self.action_type,
            date=self.date, server_date=self.server_date
        )
