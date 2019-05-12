from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq.apps.app_manager.dbaccessors import get_build_by_version
from corehq.motech.utils import b64_aes_decrypt
from custom.icds.const import (
    FILE_TYPE_CHOICE_ZIP,
    FILE_TYPE_CHOICE_DOC,
    DISPLAY_CHOICE_LIST,
    DISPLAY_CHOICE_FOOTER,
)
from custom.icds.utils.ccz_hosting import CCZHostingUtility
from custom.icds.validators import (
    LowercaseAlphanumericValidator,
)


class CCZHostingLink(models.Model):
    identifier = models.CharField(null=False, unique=True, max_length=255, db_index=True,
                                  validators=[LowercaseAlphanumericValidator])
    username = models.CharField(null=False, max_length=255)
    # b64_aes_encrypt'ed raw password is stored in DB
    password = models.CharField(null=False, max_length=255)
    domain = models.CharField(null=False, max_length=255)
    page_title = models.CharField(blank=True, max_length=255)

    def __str__(self):
        return self.identifier

    @cached_property
    def get_password(self):
        return b64_aes_decrypt(self.password)

    def to_json(self):
        from custom.icds.serializers import CCZHostingLinkSerializer
        return CCZHostingLinkSerializer(self).data

    def delete(self, *args, **kwargs):
        for ccz_hosting in CCZHosting.objects.filter(link=self):
            ccz_hosting.delete()
        super(CCZHostingLink, self).delete(*args, **kwargs)


class CCZHostingSupportingFile(models.Model):
    FILE_TYPE_CHOICES = (
        (FILE_TYPE_CHOICE_ZIP, 'zip'),
        (FILE_TYPE_CHOICE_DOC, 'document'),
    )
    DISPLAY_CHOICES = (
        (DISPLAY_CHOICE_LIST, 'list'),
        (DISPLAY_CHOICE_FOOTER, 'footer'),
    )
    domain = models.CharField(null=False, max_length=255, db_index=True)
    blob_id = models.CharField(null=False, max_length=255, db_index=True)
    file_name = models.CharField(max_length=255, blank=False)
    file_type = models.IntegerField(choices=FILE_TYPE_CHOICES)
    display = models.IntegerField(choices=DISPLAY_CHOICES)

    class Meta:
        unique_together = ('domain', 'blob_id')

    @cached_property
    def utility(self):
        return CCZHostingUtility(self)

    def delete_file(self):
        # if no other domain is using this file/doc, delete the file from blobdb
        if not (CCZHostingSupportingFile.objects.filter(blob_id=self.blob_id)
                .exclude(domain=self.domain).exists()):
            self.utility.remove_file_from_blobdb()

    def delete(self, *args, **kwargs):
        self.delete_file()
        super(CCZHostingSupportingFile, self).delete(*args, **kwargs)


class CCZHosting(models.Model):
    link = models.ForeignKey(CCZHostingLink, on_delete=models.CASCADE)
    app_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
    profile_id = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('link', 'app_id', 'version', 'profile_id')

    @cached_property
    def utility(self):
        return CCZHostingUtility(self)

    @cached_property
    def domain(self):
        return self.link.domain

    def to_json(self, app_names):
        from custom.icds.serializers import CCZHostingSerializer
        return CCZHostingSerializer(self, context={'app_names': app_names}).data

    @cached_property
    def blob_id(self):
        assert self.app_id
        assert self.version
        return "%s%s%s" % (self.app_id, self.version, self.profile_id)

    @cached_property
    def build_doc(self):
        if self.link_id and self.app_id and self.version:
            return get_build_by_version(self.link.domain, self.app_id, self.version)

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
        super(CCZHosting, self).clean()

    def save(self, *args, **kwargs):
        from custom.icds.tasks.ccz_hosting import setup_ccz_file_for_hosting
        self.full_clean()
        super(CCZHosting, self).save(*args, **kwargs)
        setup_ccz_file_for_hosting.delay(self.pk)

    def delete_ccz(self):
        # if no other link is using this app+version+profile, delete the file from blobdb
        if not (CCZHosting.objects.filter(app_id=self.app_id, version=self.version, profile_id=self.profile_id)
                .exclude(link=self.link).exists()):
            self.utility.remove_file_from_blobdb()

    def delete(self, *args, **kwargs):
        self.delete_ccz()
        super(CCZHosting, self).delete(*args, **kwargs)
