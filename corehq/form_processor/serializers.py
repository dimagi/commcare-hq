from django.utils.functional import lazy
from jsonfield import JSONField
from rest_framework import serializers

from corehq.blobs.models import BlobMeta
from corehq.form_processor.exceptions import MissingFormXml
from corehq.form_processor.models import (
    CommCareCaseIndex, CommCareCase, CaseTransaction,
    XFormInstance, XFormOperation,
    LedgerValue, CaseAttachment)


class DeletableModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, instance=None, *args, **kwargs):
        super(DeletableModelSerializer, self).__init__(instance=instance, *args, **kwargs)
        if instance is not None and not instance.is_deleted:
            self.fields.pop('deletion_id')
            self.fields.pop('deleted_on')


class XFormOperationSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user_id")

    class Meta(object):
        model = XFormOperation
        exclude = ('id', 'form', 'user_id')


class XFormAttachmentSQLSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="key")

    class Meta(object):
        model = BlobMeta
        fields = ('id', 'content_type', 'content_length')


def _serialize_form_attachments(form):
    return form.serialized_attachments


def _serialize_form_history(form):
    return list(XFormOperationSerializer(form.history, many=True).data)


lazy_serialize_form_attachments = lazy(_serialize_form_attachments, dict)
lazy_serialize_form_history = lazy(_serialize_form_history, dict)


class XFormInstanceSerializer(DeletableModelSerializer):
    _id = serializers.CharField(source='form_id')
    doc_type = serializers.CharField()
    form = serializers.JSONField(source='form_data')
    auth_context = serializers.DictField()
    openrosa_headers = serializers.DictField()

    class Meta(object):
        model = XFormInstance
        exclude = ('id', 'form_id', 'time_end', 'time_start', 'commcare_version', 'app_version')


class XFormStateField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        super(XFormStateField, self).__init__(XFormInstance.STATES, **kwargs)

    def get_attribute(self, obj):
        choice = super(serializers.ChoiceField, self).get_attribute(obj)
        readable_state = []
        for state, state_slug in self.choices.items():
            if choice & state:
                readable_state.append(state_slug)
        return ' / '.join(readable_state)


class JsonFieldSerializerMixin(object):
    serializer_field_mapping = {}
    serializer_field_mapping.update(DeletableModelSerializer.serializer_field_mapping)
    serializer_field_mapping[JSONField] = serializers.JSONField


class XFormInstanceRawDocSerializer(JsonFieldSerializerMixin, DeletableModelSerializer):
    state = XFormStateField()
    history = XFormOperationSerializer(many=True, read_only=True)
    form = serializers.JSONField(source='form_data')
    external_blobs = serializers.JSONField(source='serialized_attachments')

    def __init__(self, instance=None, *args, **kwargs):
        super(XFormInstanceRawDocSerializer, self).__init__(instance=instance, *args, **kwargs)
        if instance is not None:
            try:
                instance.get_xml()
            except MissingFormXml:
                self.fields.pop('form')

    class Meta(object):
        model = XFormInstance
        fields = '__all__'


class CommCareCaseIndexSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField()
    relationship = serializers.CharField()

    class Meta(object):
        model = CommCareCaseIndex
        fields = ('case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship')


class CaseTransactionActionSerializer(serializers.ModelSerializer):
    xform_id = serializers.CharField(source='form_id')
    date = serializers.DateTimeField(source='client_date')

    class Meta(object):
        model = CaseTransaction
        fields = ('xform_id', 'server_date', 'date', 'sync_log_id')


class CaseTransactionActionRawDocSerializer(JsonFieldSerializerMixin, CaseTransactionActionSerializer):
    type = serializers.CharField(source='readable_type')

    class Meta(object):
        model = CaseTransaction
        fields = ('form_id', 'server_date', 'date', 'sync_log_id', 'type', 'details')


class CommCareCaseRawDocSerializer(JsonFieldSerializerMixin, DeletableModelSerializer):
    indices = CommCareCaseIndexSerializer(many=True, read_only=True)
    transactions = CaseTransactionActionRawDocSerializer(
        many=True, read_only=True, source='non_revoked_transactions')

    class Meta(object):
        model = CommCareCase
        fields = '__all__'


class CaseAttachmentSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = CaseAttachment
        fields = (
            'content_type',
            'content_length',
            'name',
        )


def _serialize_case_indices(case):
    return list(CommCareCaseIndexSerializer(case.indices, many=True).data)


def _serialize_case_transactions(case):
    return list(CaseTransactionActionSerializer(case.non_revoked_transactions, many=True).data)


def _serialize_case_xform_ids(case):
    return list(case.xform_ids)


def _serialize_case_attachments(case):
    return dict(case.serialized_attachments)


lazy_serialize_case_indices = lazy(_serialize_case_indices, list)
lazy_serialize_case_transactions = lazy(_serialize_case_transactions, list)
lazy_serialize_case_xform_ids = lazy(_serialize_case_xform_ids, list)
lazy_serialize_case_attachments = lazy(_serialize_case_attachments, dict)


class CommCareCaseSerializer(DeletableModelSerializer):
    _id = serializers.CharField(source='case_id')
    doc_type = serializers.CharField()
    user_id = serializers.CharField(source='modified_by')
    case_json = serializers.JSONField()

    class Meta(object):
        model = CommCareCase
        exclude = ('id',)


class CommCareCaseAPISerializer(serializers.ModelSerializer):
    """This serializer is for presenting a case in json for APIs to access"""
    user_id = serializers.CharField(source='modified_by')
    date_closed = serializers.DateTimeField(source='closed_on')
    date_modified = serializers.DateTimeField(source='modified_on')
    properties = serializers.JSONField(source='get_properties_in_api_format')
    server_date_modified = serializers.DateTimeField(source='server_modified_on')
    indices = serializers.JSONField(source='get_index_map')
    attachments = serializers.JSONField(source='get_attachment_map')
    reverse_indices = serializers.JSONField(source='get_reverse_index_map')

    def __init__(self, *args, **kwargs):
        lite = kwargs.pop('lite', False)
        if lite:
            self.fields.pop('reverse_indices')
        super(CommCareCaseAPISerializer, self).__init__(*args, **kwargs)

    class Meta(object):
        model = CommCareCase
        fields = (
            'domain',
            'case_id',
            'user_id',
            'closed',
            'xform_ids',
            'date_closed',
            'date_modified',
            'server_date_modified',
            'properties',
            'indices',
            'reverse_indices',
            'attachments',
        )


class LedgerValueSerializer(serializers.ModelSerializer):
    _id = serializers.CharField(source='ledger_id')
    location_id = serializers.CharField()
    case_id = serializers.CharField()

    def __init__(self, *args, **kwargs):
        include_location_id = kwargs.pop('include_location_id', False)
        if not include_location_id:
            self.fields.pop('location_id')
        super(LedgerValueSerializer, self).__init__(*args, **kwargs)

    class Meta(object):
        model = LedgerValue
        exclude = ('id', 'case')
