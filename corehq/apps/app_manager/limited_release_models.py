from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext as _
from memoized import memoized

from corehq.apps.app_manager.dbaccessors import get_app, get_build_by_version
from corehq.apps.app_manager.util import (
    expire_get_latest_app_release_by_location_cache,
    get_latest_app_release_by_location,
    get_latest_enabled_build_for_profile,
    get_latest_enabled_versions_per_profile,
)
from corehq.apps.locations.models import SQLLocation


class AppReleaseByLocation(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    location = models.ForeignKey(SQLLocation, on_delete=models.CASCADE, to_field='location_id')
    build_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
    active = models.BooleanField(default=True)
    activated_on = models.DateTimeField(null=True, blank=True)
    deactivated_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (("domain", "build_id", "location", "version"),)

    def save(self, *args, **kwargs):
        super(AppReleaseByLocation, self).save(*args, **kwargs)
        expire_get_latest_app_release_by_location_cache(self)

    @property
    @memoized
    def build(self):
        return get_app(self.domain, self.build_id)

    def clean(self):
        if self.active:
            if not self.build.is_released:
                raise ValidationError({'version': _("Version {} not released. Please mark it as released to add "
                                                    "restrictions.").format(self.build.version)})
            enabled_release = get_latest_app_release_by_location(self.domain, self.location.location_id,
                                                                 self.app_id)
            if enabled_release and enabled_release.version > self.version:
                raise ValidationError({'version': _("Higher version {} already enabled for this application and "
                                                    "location").format(enabled_release.version)})

    @classmethod
    def update_status(cls, domain, app_id, build_id, location_id, version, active):
        """
        create a new object or just set the status of an existing one with provided
        domain, app_id, build_id, location_id and version to the status passed
        :param build_id: id of the build corresponding to the version
        """
        try:
            release = AppReleaseByLocation.objects.get(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        except cls.DoesNotExist:
            release = AppReleaseByLocation(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        release.activate() if active else release.deactivate()

    def deactivate(self):
        self.active = False
        self.deactivated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def activate(self):
        self.active = True
        self.activated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def to_json(self):
        return {
            'location': self.location.get_path_display(),
            'app': self.app_id,
            'build_id': self.build_id,
            'version': self.version,
            'active': self.active,
            'id': self._get_pk_val(),
            'activated_on': (datetime.datetime.strftime(self.activated_on, '%Y-%m-%d  %H:%M:%S')
                             if self.activated_on else None),
            'deactivated_on': (datetime.datetime.strftime(self.deactivated_on, '%Y-%m-%d %H:%M:%S')
                               if self.deactivated_on else None),
        }


class LatestEnabledBuildProfiles(models.Model):
    # ToDo: this would be deprecated after AppReleaseByLocation is released and
    # this model's entries are migrated to the new location specific model
    domain = models.CharField(max_length=255, null=False, default='')
    app_id = models.CharField(max_length=255)
    build_profile_id = models.CharField(max_length=255)
    version = models.IntegerField()
    build_id = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super(LatestEnabledBuildProfiles, self).save(*args, **kwargs)
        self.expire_cache(self.domain)

    @property
    def build(self):
        if not hasattr(self, '_build'):
            self._build = get_build_by_version(self.domain, self.app_id, self.version)['value']
        return self._build

    def clean(self):
        if self.active:
            if not self.build['is_released']:
                raise ValidationError({
                    'version': _("Version {} not released. Can not enable profiles for unreleased versions"
                                 ).format(self.build['version'])
                })
            latest_enabled_build_profile = LatestEnabledBuildProfiles.for_app_and_profile(
                app_id=self.build['copy_of'],
                build_profile_id=self.build_profile_id
            )
            if latest_enabled_build_profile and latest_enabled_build_profile.version > self.version:
                raise ValidationError({
                    'version': _("Latest version available for this profile is {}, which is "
                                 "higher than this version. Disable any higher versions first."
                                 ).format(latest_enabled_build_profile.version)})

    @classmethod
    def update_status(cls, build, build_profile_id, active):
        """
        create a new object or just set the status of an existing one for an app
        build and build profile to the status passed
        :param active: to be set as active, True/False
        """
        app_id = build.copy_of
        build_id = build.get_id
        version = build.version
        try:
            build_profile = LatestEnabledBuildProfiles.objects.get(
                app_id=app_id,
                version=version,
                build_profile_id=build_profile_id,
                build_id=build_id
            )
        except cls.DoesNotExist:
            build_profile = LatestEnabledBuildProfiles(
                app_id=app_id,
                version=version,
                build_profile_id=build_profile_id,
                build_id=build_id,
                domain=build.domain
            )
        # assign it to avoid re-fetching during validations
        build_profile._build = build
        build_profile.activate() if active else build_profile.deactivate()

    def activate(self):
        self.active = True
        self.full_clean()
        self.save()

    def deactivate(self):
        self.active = False
        self.full_clean()
        self.save()

    @classmethod
    def for_app_and_profile(cls, app_id, build_profile_id):
        return cls.objects.filter(
            app_id=app_id,
            build_profile_id=build_profile_id,
            active=True
        ).order_by('-version').first()

    def expire_cache(self, domain):
        get_latest_enabled_build_for_profile.clear(domain, self.build_profile_id)
        get_latest_enabled_versions_per_profile.clear(self.app_id)

    def to_json(self, app_names):
        from corehq.apps.app_manager.serializers import LatestEnabledBuildProfileSerializer
        return LatestEnabledBuildProfileSerializer(self, context={'app_names': app_names}).data
