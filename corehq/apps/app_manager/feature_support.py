from distutils.version import LooseVersion, Version


class CommCareFeatureSupportMixin(object):
    # overridden by subclass
    build_version = LooseVersion('')

    def _require_minimum_version(self, minimum_version):
        assert isinstance(self.build_version, Version)
        assert isinstance(minimum_version, (basestring, Version))
        return self.build_version >= minimum_version

    @property
    def enable_multi_sort(self):
        """
        Multi (tiered) sort is supported by apps version 2.2 or higher
        """
        return self._require_minimum_version('2.2')

    @property
    def enable_multimedia_case_property(self):
        """
        Multimedia case properties are supported by apps version 2.6 or higher
        """
        return self._require_minimum_version('2.6')

    @property
    def enable_relative_suite_path(self):
        return self._require_minimum_version('2.12')

    @property
    def enable_local_resource(self):
        """
        There was a CommCare bug that was triggered by having
        both a local and remote authority for a resource.
        This bug was fixed in 2.13.

        see comment at
        https://github.com/dimagi/commcare-hq/pull/3511#discussion_r13159938

        """
        return self._require_minimum_version('2.13')

    @property
    def enable_offline_install(self):
        """
        Offline Android Install is supported by apps version 2.13 or higher
        """
        # this is kind of stupid,
        # since this amounts to requiring a min version of 2.13
        # but this feature was basically ready in 2.12
        # but could not be used until the local resource bug was fixed.
        # I wanted to record that dependency
        return (self.enable_local_resource
                and self._require_minimum_version('2.12'))

    @property
    def enable_auto_gps(self):
        return self._require_minimum_version('2.14')
