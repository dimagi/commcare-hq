from django.db import models
from corehq.apps.sofabed.exceptions import (
    InvalidFormUpdateException,
    InvalidMetaBlockException,
    InvalidCaseUpdateException,
    InvalidDomainException)

CASE_NAME_LEN = 512

MISSING_APP_ID = '_MISSING_APP_ID'


class BaseDataIndex(models.Model):

    @classmethod
    def get_instance_id(cls, item):
        raise NotImplementedError()

    @classmethod
    def from_instance(cls, instance):
        """
        Factory method for creating these objects from an instance doc
        """
        ret = cls()
        ret.update(instance)
        return ret

    @classmethod
    def create_or_update_from_instance(cls, instance):
        """
        Create or update an object in the database from an CommCareCase
        """
        try:
            val = cls.objects.get(pk=cls.get_instance_id(instance))
        except cls.DoesNotExist:
            val = cls.from_instance(instance)
            val.save()
        else:
            if not val.matches_exact(instance):
                val.update(instance)
                val.save()

        return val

    def __unicode__(self):
        return "%s: %s" % (self.__class__.__name__, self.pk)

    class Meta:
        abstract = True


class CaseData(BaseDataIndex):
    """
    Data about a CommCareCase.
    See CommCareCase class
    """
    case_id = models.CharField(unique=True, primary_key=True, max_length=128)
    domain = models.CharField(max_length=128, db_index=True)
    version = models.CharField(max_length=10, null=True)
    type = models.CharField(max_length=128, db_index=True, null=True)
    closed = models.BooleanField(db_index=True, default=False)
    user_id = models.CharField(max_length=128, db_index=True, null=True)
    owner_id = models.CharField(max_length=128, db_index=True, null=True)
    opened_on = models.DateTimeField(db_index=True, null=True)
    opened_by = models.CharField(max_length=128, db_index=True, null=True)
    closed_on = models.DateTimeField(db_index=True, null=True)
    closed_by = models.CharField(max_length=128, db_index=True, null=True)
    modified_on = models.DateTimeField(db_index=True)
    modified_by = models.CharField(max_length=128, null=True)
    server_modified_on = models.DateTimeField(db_index=True, null=True)
    name = models.CharField(max_length=CASE_NAME_LEN, null=True)
    external_id = models.CharField(max_length=128, null=True)

    # owner_id || user_id
    case_owner = models.CharField(max_length=128, null=True, db_index=True)

    @classmethod
    def get_instance_id(cls, instance):
        return instance.case_id

    def update(self, case):
        """
        Update this object based on a CommCareCase doc
        """
        is_new = not self.case_id
        case_id = self.get_instance_id(case)

        if self.case_id and self.case_id != case_id:
            raise InvalidCaseUpdateException(
                "Tried to update CaseData %s with different "
                "case id %s!" % (self.case_id, case_id)
            )

        if case.name and len(case.name) > CASE_NAME_LEN:
            name = case.name[:CASE_NAME_LEN-3] + '...'
        else:
            name = case.name

        self.case_id = case_id
        self.domain = case.domain
        self.version = case.version
        self.type = case.type
        self.closed = case.closed
        self.owner_id = case.owner_id
        self.user_id = case.user_id
        self.opened_on = case.opened_on
        self.opened_by = case.opened_by
        self.closed_on = case.closed_on
        self.closed_by = case.closed_by
        self.modified_on = case.modified_on
        self.modified_by = case.user_id
        self.server_modified_on = case.server_modified_on
        self.name = name
        self.external_id = case.external_id
        self.case_owner = case.owner_id or case.user_id

        if not is_new:
            CaseActionData.objects.filter(case_id=case_id).delete()
            CaseIndexData.objects.filter(case_id=case_id).delete()

        self.actions = [CaseActionData.from_instance(case, action, i) for i, action in enumerate(case.actions)]
        self.indices = [CaseIndexData.from_instance(index) for index in case.indices]

    def matches_exact(self, case):
        basic_match = (
            self.modified_on == case.modified_on and
            self.modified_by == case.user_id and
            self.closed == case.closed and
            self.closed_on == case.closed_on and
            self.closed_by == case.closed_by and
            self.server_modified_on == case.server_modified_on and
            self.case_id == case.case_id and
            self.domain == case.domain and
            self.version == case.version and
            self.type == case.type and
            self.owner_id == case.owner_id and
            self.user_id == case.user_id and
            self.opened_on == case.opened_on and
            self.opened_by == case.opened_by and
            self.name == case.name and
            self.external_id == case.external_id
        )

        if not basic_match:
            return False

        this_actions = self.actions.order_by('index').all()
        if not len(case.actions) == len(this_actions):
            return False

        for i, action in enumerate(case.actions):
            if not this_actions[i].matches_exact(action, i):
                return False

        return True

    class Meta:
        app_label = 'sofabed'


class CaseActionData(models.Model):
    """
    Data about a CommCareCase action.
    See CommCareCaseAction class
    """
    case = models.ForeignKey(CaseData, related_name='actions')
    index = models.IntegerField()
    action_type = models.CharField(max_length=64, db_index=True)
    user_id = models.CharField(max_length=128, db_index=True, null=True)
    date = models.DateTimeField(db_index=True)
    server_date = models.DateTimeField(null=True)
    xform_id = models.CharField(max_length=128, null=True)
    xform_xmlns = models.CharField(max_length=128, null=True)
    sync_log_id = models.CharField(max_length=128, null=True)

    # de-normalized fields
    domain = models.CharField(max_length=128, null=True, db_index=True)
    case_owner = models.CharField(max_length=128, null=True, db_index=True)
    case_type = models.CharField(max_length=128, null=True, db_index=True)

    def __unicode__(self):
        return "CaseAction: {xform}: {type} - {date} ({server_date})".format(
            xform=self.xform_id, type=self.action_type,
            date=self.date, server_date=self.server_date
        )

    @classmethod
    def from_instance(cls, case, action, index):
        ret = cls()

        ret.domain = case.domain
        ret.case_type = case.type
        ret.case_owner = case.owner_id or case.user_id

        ret.index = index
        ret.action_type = action.action_type
        ret.user_id = action.user_id
        ret.date = action.date
        ret.server_date = action.server_date
        ret.xform_id = action.xform_id
        ret.xform_xmlns = action.xform_xmlns
        ret.sync_log_id = action.sync_log_id
        return ret

    def matches_exact(self, action, index):
        return (
            self.index == index and
            self.date == action.date and
            self.server_date == action.server_date and
            self.xform_id == action.xform_id and
            self.action_type == action.action_type and
            self.user_id == action.user_id and
            self.xform_xmlns == action.xform_xmlns and
            self.sync_log_id == action.sync_log_id
        )

    class Meta:
        app_label = 'sofabed'
        unique_together = ("case", "index")


class CaseIndexData(models.Model):
    """
    Data about a CommCareCase Index.
    See CommCareCaseIndex class
    """
    case = models.ForeignKey(CaseData, related_name='indices')
    identifier = models.CharField(max_length=64, db_index=True)
    referenced_type = models.CharField(max_length=64, db_index=True)
    referenced_id = models.CharField(max_length=128, db_index=True)

    def __unicode__(self):
        return "CaseIndex: %(identifier)s ref: (type: %(ref_type)s, id: %(ref_id)s)" % {
            "identifier": self.identifier,
            "ref_type": self.referenced_type,
            "ref_id": self.referenced_id
        }

    @classmethod
    def from_instance(cls, index):
        ret = cls()
        ret.identifier = index.identifier
        ret.referenced_type = index.referenced_type
        ret.referenced_id = index.referenced_id
        return ret

    class Meta:
        app_label = 'sofabed'
