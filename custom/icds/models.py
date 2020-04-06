import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version
from custom.icds.const import (
    DISPLAY_CHOICE_CUSTOM,
    DISPLAY_CHOICE_FOOTER,
    DISPLAY_CHOICE_LIST,
    FILE_TYPE_CHOICE_DOC,
    FILE_TYPE_CHOICE_ZIP,
)
from custom.icds.utils.hosted_ccz import HostedCCZUtility
from custom.icds.validators import HostedCCZLinkIdentifierValidator
from custom.nic_compliance.utils import hash_password


class HostedCCZLink(models.Model):
    identifier = models.CharField(null=False, unique=True, max_length=255, db_index=True,
                                  validators=[HostedCCZLinkIdentifierValidator])
    username = models.CharField(null=False, max_length=255)
    password = models.CharField(null=False, max_length=255)
    domain = models.CharField(null=False, max_length=255)
    page_title = models.CharField(blank=True, max_length=255)

    def __str__(self):
        return self.identifier

    def to_json(self):
        from custom.icds.serializers import HostedCCZLinkSerializer
        return HostedCCZLinkSerializer(self).data

    def save(self, *args, **kwargs):
        if not self.pk:
            self.password = hash_password(self.password)
        self.full_clean()
        super(HostedCCZLink, self).save(*args, **kwargs)


class HostedCCZSupportingFile(models.Model):
    FILE_TYPE_CHOICES = (
        (FILE_TYPE_CHOICE_ZIP, 'zip'),
        (FILE_TYPE_CHOICE_DOC, 'document'),
    )
    DISPLAY_CHOICES = (
        (DISPLAY_CHOICE_LIST, 'list'),
        (DISPLAY_CHOICE_FOOTER, 'footer'),
        (DISPLAY_CHOICE_CUSTOM, 'custom'),
    )
    domain = models.CharField(null=False, max_length=255, db_index=True)
    blob_id = models.CharField(null=False, max_length=255, db_index=True)
    file_name = models.CharField(max_length=255, blank=False)
    file_type = models.IntegerField(choices=FILE_TYPE_CHOICES)
    display = models.IntegerField(choices=DISPLAY_CHOICES)

    class Meta:
        unique_together = ('domain', 'blob_id')

    def __str__(self):
        return self.file_name

    @cached_property
    def utility(self):
        return HostedCCZUtility(self)

    def delete_file(self):
        # if no other domain is using this file/doc, delete the file from blobdb
        if not (HostedCCZSupportingFile.objects.filter(blob_id=self.blob_id)
                .exclude(domain=self.domain).exists()):
            self.utility.remove_file_from_blobdb()

    def delete(self, *args, **kwargs):
        self.delete_file()
        super(HostedCCZSupportingFile, self).delete(*args, **kwargs)

    @classmethod
    def create(cls, domain, file_name, file_type, display, file_obj):
        supporting_file = cls(
            file_name=file_name, file_type=file_type, display=display,
            domain=domain, blob_id=uuid.uuid4().hex
        )
        supporting_file.full_clean()
        supporting_file.save()
        supporting_file.utility.store_file_in_blobdb(file_obj, file_name)
        return supporting_file.utility.file_exists()


class HostedCCZ(models.Model):
    PENDING = 'pending'
    BUILDING = 'building'
    FAILED = 'failed'
    COMPLETED = 'completed'
    STATUSES = [PENDING, BUILDING, FAILED, COMPLETED]
    link = models.ForeignKey(HostedCCZLink, on_delete=models.CASCADE)
    app_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
    profile_id = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=255, null=False, blank=False, default='pending',
                              choices=((PENDING, _('Pending')),
                                       (BUILDING, _('Building')),
                                       (FAILED, _('Failed')),
                                       (COMPLETED, _('Completed')),
                                       ))

    class Meta:
        unique_together = ('link', 'app_id', 'version', 'profile_id')

    @cached_property
    def utility(self):
        return HostedCCZUtility(self)

    @cached_property
    def domain(self):
        return self.link.domain

    def to_json(self):
        from custom.icds.serializers import HostedCCZSerializer
        return HostedCCZSerializer(self).data

    @cached_property
    def blob_id(self):
        assert self.app_id
        assert self.version
        return "%s%s%s" % (self.app_id, self.version, self.profile_id)

    @cached_property
    def build_doc(self):
        if self.link_id and self.app_id and self.version:
            return get_build_doc_by_version(self.domain, self.app_id, self.version)

    @cached_property
    def build_profile(self):
        if self.profile_id and self.build_doc:
            return self.build_doc['build_profiles'].get(self.profile_id)

    def clean(self):
        if not self.build_doc:
            raise ValidationError({
                'version': _("Build not found for app {} and version {}.").format(
                    self.app_id, self.version
                )
            })
        if not self.build_doc['is_released']:
            raise ValidationError({
                'version': _("Version not released. Please mark it as released.")})
        if not self.file_name:
            self.file_name = "%s-v%s" % (self.build_doc['name'], self.version)
        super(HostedCCZ, self).clean()

    def save(self, *args, **kwargs):
        from custom.icds.tasks.hosted_ccz import setup_ccz_file_for_hosting
        self.full_clean()
        email = kwargs.pop('email') if 'email' in kwargs else None
        file_exists = self.utility.file_exists()
        if file_exists:
            self.status = self.COMPLETED
        super(HostedCCZ, self).save(*args, **kwargs)
        if not file_exists:
            setup_ccz_file_for_hosting.delay(self.pk, user_email=email)

    def delete_ccz(self):
        # if no other link is using this app+version+profile, delete the file from blobdb
        if not (HostedCCZ.objects.filter(app_id=self.app_id, version=self.version, profile_id=self.profile_id)
                .exclude(link=self.link).exists()):
            self.utility.remove_file_from_blobdb()

    def delete(self, *args, **kwargs):
        self.delete_ccz()
        super(HostedCCZ, self).delete(*args, **kwargs)

    def update_status(self, new_status):
        assert new_status in self.STATUSES
        HostedCCZ.objects.filter(id=self.pk).update(status=new_status)


class HostedCCZCustomSupportingFile(models.Model):
    link = models.ForeignKey(HostedCCZLink, on_delete=models.PROTECT)
    file = models.ForeignKey(HostedCCZSupportingFile, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.file) + "@" + str(self.link)


def delete_ccz_for_link(sender, instance, **kwargs):
    for hosted_ccz in HostedCCZ.objects.filter(link=instance):
        hosted_ccz.delete_ccz()


pre_delete.connect(delete_ccz_for_link, sender=HostedCCZLink)
