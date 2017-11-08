from __future__ import absolute_import
from corehq.apps.app_manager.models import validate_property, CommentMixin
from corehq.apps.app_manager.util import is_valid_case_type, version_key
from corehq.apps.app_manager.id_strings import _format_to_regex
from corehq.apps.app_manager import xform_builder

__test__ = {
    'is_valid_case_type': is_valid_case_type,
    'version_key': version_key,
    '_format_to_regex': _format_to_regex,
    'validate_property': validate_property,
    'xform_builder': xform_builder,
    'CommentMixinTest': CommentMixin,
}
