from __future__ import absolute_import
from __future__ import unicode_literals
from distutils.version import LooseVersion, Version
from django.conf import settings
import six

from corehq.util.python_compatibility import soft_assert_type_text


class CommCareFeatureSupportMixin(object):
    # overridden by subclass
    build_version = LooseVersion('')

    def _require_minimum_version(self, minimum_version):
        if settings.UNIT_TESTING and self.build_version is None:
            return False
        assert isinstance(self.build_version, Version)
        assert isinstance(minimum_version, six.string_types + (Version,))
        if isinstance(minimum_version, six.string_types):
            soft_assert_type_text(minimum_version)
            minimum_version = LooseVersion(minimum_version)
        return self.build_version and self.build_version >= minimum_version

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

    @property
    def enable_group_in_field_list(self):
        """
        Groups and repeat groups inside of a field list supported by apps
        version 2.16 or higher
        """
        return self._require_minimum_version('2.16')

    @property
    def enable_post_form_workflow(self):
        """
        Post form workflow is supported by apps version 2.9 or higher
        """
        return self._require_minimum_version('2.9')

    @property
    def enable_module_filtering(self):
        """
        Filtering modules is supported by apps version 2.20 or higher
        """
        return self._require_minimum_version('2.20')

    @property
    def enable_localized_menu_media(self):
        """
        Forms/Modules can have language-specific icon/audio for apps
        version 2.21 or higher
        """
        return self._require_minimum_version('2.21')

    @property
    def enable_case_list_icon_dynamic_width(self):
        """
        In 2.22 and higher, case list icon column is sized based on actual image width.
        """
        # temporarily disabled due to issue on mobile side handling exact pixel widths.
        # will look into it when there is a little more time. @orangejenny
        # return self._require_minimum_version('2.22')
        return False

    @property
    def enable_image_resize(self):
        """
        Image resize only supported > 2.23
        """
        return self._require_minimum_version('2.23')

    @property
    def enable_markdown_in_groups(self):
        """
        Markdown in groups only supported > 2.23
        """
        return self._require_minimum_version('2.23')

    @property
    def enable_case_list_sort_blanks(self):
        """
        Ability to control where blanks sort for case list sort properties only supported > 2.35
        """
        return self._require_minimum_version('2.35')

    @property
    def enable_detail_print(self):
        """
        Ability to print case detail screen, based on an HTML template, only supported > 2.35
        """
        return self._require_minimum_version('2.35')

    @property
    def supports_practice_users(self):
        """
        Ability to configure practice mobile workers for apps
        """
        return self._require_minimum_version('2.26')

    @property
    def enable_sorted_itemsets(self):
        """
        Enable sorted itemsets in the form builder.
        """
        return self._require_minimum_version('2.38')

    @property
    def supports_update_prompts(self):
        """
        Ability to configure apk/app update checks
        """
        return self._require_minimum_version('2.38')

    @property
    def enable_remote_requests(self):
        """
        Enable Remote Request question type in the form builder.
        """
        return self._require_minimum_version('2.40')

    @property
    def enable_training_modules(self):
        return self._require_minimum_version('2.43')
