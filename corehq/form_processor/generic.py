import datetime
import re
from dimagi.ext.jsonobject import (
    JsonObject,
    StringProperty,
    DictProperty,
    BooleanProperty,
    DateTimeProperty,
    ListProperty,
    IntegerProperty,
)
from jsonobject.base import DefaultProperty

from casexml.apps.case import const
from couchforms.jsonobject_extensions import GeoPointProperty
from dimagi.utils.decorators.memoized import memoized


class GenericXFormOperation(JsonObject):
    """
    Simple structure to represent something happening to a form.

    Currently used just by the archive workflow.
    """
    user = StringProperty()
    date = DateTimeProperty(default=datetime.datetime.utcnow)
    operation = StringProperty()  # e.g. "archived", "unarchived"


class GenericMetadata(JsonObject):
    """
    Metadata of an xform, from a meta block structured like:

        <Meta>
            <timeStart />
            <timeEnd />
            <instanceID />
            <userID />
            <deviceID />
            <deprecatedID />
            <username />

            <!-- CommCare extension -->
            <appVersion />
            <location />
        </Meta>

    See spec: https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema

    username is not part of the spec but included for convenience
    """
    timeStart = DateTimeProperty()
    timeEnd = DateTimeProperty()
    instanceID = StringProperty()
    userID = StringProperty()
    deviceID = StringProperty()
    deprecatedID = StringProperty()
    username = StringProperty()
    appVersion = StringProperty()
    location = GeoPointProperty()


class GenericXFormInstance(JsonObject):
    """A generic JSON representation of an XForm"""
    id = StringProperty()
    domain = StringProperty()
    app_id = StringProperty()
    orig_id = StringProperty()
    deprecated_form_id = StringProperty()
    xmlns = StringProperty()
    form = DictProperty()
    received_on = DateTimeProperty()
    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = BooleanProperty(default=False)
    history = ListProperty(GenericXFormOperation)
    auth_context = DictProperty()
    submit_ip = StringProperty()
    path = StringProperty()
    openrosa_headers = DictProperty()
    last_sync_token = StringProperty()
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = DefaultProperty()
    build_id = StringProperty()
    export_tag = DefaultProperty(name='#export_tag')

    is_error = BooleanProperty(default=False)
    is_duplicate = BooleanProperty(default=False)
    is_deprecated = BooleanProperty(default=False)
    is_archived = BooleanProperty(default=False)

    _metadata = None

    @property
    def metadata(self):
        return self._metadata

    def get_data(self, xpath):
        """
        Get data from a document from an xpath, returning None if the value isn't found.
        Copied from safe_index
        """
        return GenericXFormInstance._get_data(self, xpath.split('/'))

    @staticmethod
    def _get_data(xform, keys):
        if len(keys) == 1:
            # first check dict lookups, in case of conflicting property names
            # with methods (e.g. case/update --> a dict's update method when
            # it should be the case block's update block.
            try:
                if keys[0] in xform:
                    return xform[keys[0]]
            except Exception:
                return getattr(xform, keys[0], None)
        else:
            return GenericXFormInstance._get_data(GenericXFormInstance._get_data(xform, [keys[0]]), keys[1:])


class GenericFormAttachment(JsonObject):
    name = StringProperty()
    content = StringProperty()


class GenericCommCareCaseIndex(JsonObject):
    identifier = StringProperty()
    referenced_type = StringProperty()
    referenced_id = StringProperty()
    # relationship = "child" for index to a parent case (default)
    # relationship = "extension" for index to a host case
    relationship = StringProperty('child', choices=['child', 'extension'])


class GenericCommCareCaseAttachment(JsonObject):
    identifier = StringProperty()
    attachment_src = StringProperty()
    attachment_from = StringProperty()
    attachment_name = StringProperty()
    server_mime = StringProperty()  # Server detected MIME
    server_md5 = StringProperty()  # Couch detected hash

    attachment_size = IntegerProperty()  # file size
    attachment_properties = DictProperty()  # width, height, other relevant metadata


class GenericCommCareCaseAction(JsonObject):
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
    indices = ListProperty(GenericCommCareCaseIndex)
    attachments = DictProperty(GenericCommCareCaseAttachment)

    deprecated = False


class GenericCommCareCase(JsonObject):
    """
    A case, taken from casexml.  This represents the latest
    representation of the case - the result of playing all
    the actions in sequence.
    """
    id = StringProperty()
    domain = StringProperty()
    export_tag = ListProperty(unicode)
    xform_ids = ListProperty(unicode)

    external_id = StringProperty()
    opened_on = DateTimeProperty()
    modified_on = DateTimeProperty()
    type = StringProperty()
    closed = BooleanProperty(default=False)
    closed_on = DateTimeProperty()
    user_id = StringProperty()
    owner_id = StringProperty()
    opened_by = StringProperty()
    closed_by = StringProperty()

    actions = ListProperty(GenericCommCareCaseAction)
    name = StringProperty()
    version = StringProperty()
    indices = ListProperty(GenericCommCareCaseIndex)
    case_attachments = DictProperty(GenericCommCareCaseAttachment)
    server_modified_on = DateTimeProperty()

    @property
    def case_id(self):
        return self.id

    @property
    @memoized
    def reverse_indices(self):
        from corehq.form_processor.interfaces import FormProcessorInterface
        return FormProcessorInterface.get_reverse_indices(self.domain, self.id)

    def has_index(self, id):
        return id in (i.identifier for i in self.indices)

    def get_index(self, id):
        found = filter(lambda i: i.identifier == id, self.indices)
        if found:
            assert(len(found) == 1)
            return found[0]
        return None

    def dynamic_case_properties(self):
        """(key, value) tuples sorted by key"""
        from jsonobject.base import get_dynamic_properties
        json = self.to_json()
        wrapped_case = self
        if type(self) != GenericCommCareCase:
            wrapped_case = GenericCommCareCase.wrap(self._doc)

        # should these be removed before converting to generic?
        exclude = ['computed_modified_on_', 'computed_', 'doc_type', 'initial_processing_complete']
        return sorted([
            (key, json[key]) for key in get_dynamic_properties(wrapped_case)
            if re.search(r'^[a-zA-Z]', key) and key not in exclude
        ])
