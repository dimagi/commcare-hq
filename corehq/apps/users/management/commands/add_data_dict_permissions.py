from django.core.management.base import BaseCommand

from django.db.models import Q

from dimagi.utils.chunked import chunked
from corehq.util.log import with_progress_bar
from corehq.apps.users.permissions import EXPORT_PERMISSIONS
from corehq.apps.users.models import RolePermission, HqPermissions
from corehq.apps.users.models_role import Permission, UserRole
from corehq.toggles import DATA_DICTIONARY, DATA_FILE_DOWNLOAD
from corehq.apps.accounting.utils import get_domains_with_privilege


class Command(BaseCommand):
    help = "Adds data dictionary permission to user role if not already present and edit tab is viewable."

    def handle(self, **options):
        Permission.create_all()

        user_role_ids_to_migrate = get_user_role_ids_to_migrate()

        for chunk in with_progress_bar(chunked(user_role_ids_to_migrate, 1000),
                                    length=len(user_role_ids_to_migrate)):
            for role in UserRole.objects.filter(id__in=chunk):
                permissions = role.permissions
                permissions.edit_data_dict = True
                permissions.view_data_dict = True
                role.set_permissions(permissions.to_list())


def get_user_role_ids_to_migrate():
    # Need to get domains with privilege and those with the toggle still enabled
    data_dict_domains = get_domains_with_privilege(DATA_DICTIONARY.slug) + DATA_DICTIONARY.get_enabled_domains()

    return (UserRole.objects
        .filter(domain__in=data_dict_domains)
        .exclude(role_already_migrated())
        .filter(role_can_view_data_tab())
        .distinct()
        .values_list("id", flat=True))


def role_already_migrated() -> Q:
    return Q(rolepermission__permission_fk__value=HqPermissions.edit_data_dict.name)


def role_can_view_data_tab() -> Q:
    can_edit_commcare_data = build_role_can_edit_commcare_data_q_object()
    can_export_data = build_role_can_export_data_q_object()
    can_download_data_files = build_role_can_download_data_files_q_object()

    return (can_edit_commcare_data | can_export_data | can_download_data_files)


def build_role_can_edit_commcare_data_q_object() -> Q:
    return Q(rolepermission__permission_fk__value=HqPermissions.edit_data.name)


def build_role_can_export_data_q_object() -> Q:
    can_view_commcare_export_reports = Q(allow_all=True)
    for export_permission in EXPORT_PERMISSIONS:
        can_view_commcare_export_reports.add(Q(allowed_items__contains=[export_permission]), Q.OR)
    queryset = (RolePermission.objects
                .filter(permission_fk__value=HqPermissions.view_reports.name)
                .filter(can_view_commcare_export_reports))

    return Q(rolepermission__in=queryset)


def build_role_can_download_data_files_q_object() -> Q:
    data_file_download_domains = DATA_FILE_DOWNLOAD.get_enabled_domains()

    data_file_download_feat_flag_on = Q(domain__in=data_file_download_domains)
    can_view_file_dropzone = Q(rolepermission__permission_fk__value=HqPermissions.view_file_dropzone.name)
    can_edit_file_dropzone = Q(rolepermission__permission_fk__value=HqPermissions.edit_file_dropzone.name)

    return (data_file_download_feat_flag_on & (can_view_file_dropzone | can_edit_file_dropzone))
