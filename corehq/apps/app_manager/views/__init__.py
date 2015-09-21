from corehq.apps.app_manager.views.translations import (
    upload_bulk_ui_translations,
    download_bulk_ui_translations,
    download_bulk_app_translations,
    upload_bulk_app_translations,
)
from corehq.apps.app_manager.views.download import (
    app_diff_view,
    download_app_strings,
    download_file,
    download_index,
    download_jad,
    download_jar,
    download_media_profile,
    download_media_suite,
    download_odk_media_profile,
    download_odk_profile,
    download_profile,
    download_raw_jar,
    download_suite,
    download_test_jar,
    download_user_registration,
    download_xform,
    DownloadCCZ,
)
from corehq.apps.app_manager.views.app_summary import AppSummaryView
from corehq.apps.app_manager.views.apps import (
    app_from_template,
    app_source,
    copy_app,
    copy_app_check_domain,
    default_new_app,
    delete_app,
    delete_app_lang,
    edit_app_attr,
    edit_app_langs,
    edit_app_translations,
    formdefs,
    get_app_translations,
    get_commcare_version,
    import_app,
    new_app,
    rearrange,
    rename_language,
    undo_delete_app,
    validate_language,
    view_app,
)
from corehq.apps.app_manager.views.cli import (
    direct_ccz,
    list_apps,
)
from corehq.apps.app_manager.views.download import (
    download_app_strings,
    download_file,
    download_index,
    download_jad,
    download_jar,
    download_media_profile,
    download_media_suite,
    download_odk_media_profile,
    download_odk_profile,
    download_profile,
    download_raw_jar,
    download_suite,
    download_test_jar,
    download_user_registration,
    download_xform,
    DownloadCCZ,
    validate_form_for_build,
)
from corehq.apps.app_manager.views.forms import (
    copy_form,
    delete_form,
    edit_advanced_form_actions,
    edit_careplan_form_actions,
    edit_form_actions,
    edit_form_attr,
    form_casexml,
    get_form_datums,
    get_user_registration_source,
    get_xform_source,
    new_form,
    patch_xform,
    undo_delete_form,
    view_form,
    view_user_registration,
    xform_display,
)
from corehq.apps.app_manager.views.modules import (
    delete_module,
    edit_module_attr,
    edit_module_detail_screens,
    edit_report_module,
    new_module,
    undo_delete_module,
    validate_module_for_build,
    view_module,
)
from corehq.apps.app_manager.views.multimedia import (
    multimedia_ajax,
    multimedia_list_download,
)
from corehq.apps.app_manager.views.releases import (
    current_app_version,
    delete_copy,
    odk_install,
    odk_media_qr_code,
    odk_qr_code,
    paginate_releases,
    release_build,
    release_manager,
    revert_to_copy,
    save_copy,
    short_odk_url,
    short_url,
    update_build_comment,
)
from corehq.apps.app_manager.views.schedules import (
    edit_schedule_phases,
    edit_visit_schedule,
)
from corehq.apps.app_manager.views.settings import (
    commcare_profile,
    edit_commcare_profile,
    edit_commcare_settings,
)
from corehq.apps.app_manager.views.translations import (
    download_bulk_app_translations,
    download_bulk_ui_translations,
    upload_bulk_app_translations,
    upload_bulk_ui_translations,
)
from corehq.apps.app_manager.views.form_designer import (
    form_designer,
    get_data_schema,
    user_registration_source,
)
