"""
Feature usage metric calculations (monthly collection).
"""
from corehq.apps.app_manager.const import WORKFLOW_DEFAULT

from .metric_registry import MetricDef


# Application Feature metric calculations

def calc_has_multimedia(ctx):
    """Check if any app uses multimedia (images, audio, video)."""
    return any(bool(getattr(a, 'multimedia_map', {})) for a in ctx.apps)


def calc_has_case_management(ctx):
    """Check if any app has a case list menu (offline case management)."""
    for app in ctx.apps:
        for module in app.get_modules():
            if getattr(module, 'case_type', ''):
                return True
    return False


def calc_has_eof_navigation(ctx):
    """Check if any form has non-default end-of-form navigation."""
    for app in ctx.apps:
        for module in app.get_modules():
            for form in module.get_forms():
                workflow = getattr(
                    form, 'post_form_workflow', WORKFLOW_DEFAULT,
                )
                if workflow != WORKFLOW_DEFAULT:
                    return True
    return False


def calc_has_web_apps(ctx):
    """Check if any app has Web Apps (cloudcare) enabled."""
    return any(getattr(a, 'cloudcare_enabled', False) for a in ctx.apps)


def calc_has_app_profiles(ctx):
    """Check if any app has build profiles configured."""
    return any(bool(getattr(a, 'build_profiles', {})) for a in ctx.apps)


def calc_has_save_to_case(ctx):
    """Check if any form has save-to-case actions configured."""
    for app in ctx.apps:
        for module in app.get_modules():
            for form in module.get_forms():
                actions = getattr(form, 'actions', None)
                if not actions:
                    continue
                update = getattr(actions, 'update_case', None)
                if update and getattr(update, 'update', {}):
                    return True
                open_case = getattr(actions, 'open_case', None)
                if open_case and getattr(open_case, 'name_update', None):
                    return True
    return False


def calc_has_custom_branding(ctx):
    """Check for custom branding: domain logo or app logos."""
    if ctx.domain_obj.has_custom_logo:
        return True
    for app in ctx.apps:
        if getattr(app, 'logo_refs', None):
            return True
    return False


def _not_implemented(field_name):
    def _stub(ctx):
        raise NotImplementedError(
            f'{field_name} calculation not yet implemented'
        )
    return _stub


FEATURE_METRICS = [
    # Application Features
    MetricDef('has_multimedia', 'cp_has_multimedia',
              calc_has_multimedia),
    MetricDef('has_case_management', 'cp_has_case_management',
              calc_has_case_management),
    MetricDef('has_eof_navigation', 'cp_has_eof_navigation',
              calc_has_eof_navigation),
    MetricDef('has_web_apps', 'cp_has_web_apps',
              calc_has_web_apps),
    MetricDef('has_app_profiles', 'cp_has_app_profiles',
              calc_has_app_profiles),
    MetricDef('has_save_to_case', 'cp_has_save_to_case',
              calc_has_save_to_case),
    MetricDef('has_custom_branding', 'cp_has_custom_branding',
              calc_has_custom_branding),

    # Data & Export Features
    MetricDef('form_exports', 'cp_n_form_exports',
              _not_implemented('form_exports'), is_boolean=False),
    MetricDef('case_exports_only', 'cp_n_case_exports_only',
              _not_implemented('case_exports_only'), is_boolean=False),
    MetricDef('scheduled_exports', 'cp_n_scheduled_exports',
              _not_implemented('scheduled_exports'), is_boolean=False),
    MetricDef('has_excel_dashboard', 'cp_has_excel_dashboard',
              _not_implemented('has_excel_dashboard')),
    MetricDef('case_list_explorer_reports',
              'cp_n_case_list_explorer_reports',
              _not_implemented('case_list_explorer_reports'),
              is_boolean=False),
    MetricDef('det_configs', 'cp_n_det_configs',
              _not_implemented('det_configs'), is_boolean=False),
    MetricDef('odata_feeds', 'cp_n_odata_feeds',
              _not_implemented('odata_feeds'), is_boolean=False),
    MetricDef('linked_domains', 'cp_n_linked_domains',
              _not_implemented('linked_domains'), is_boolean=False),
    MetricDef('has_case_deduplication', 'cp_has_case_deduplication',
              _not_implemented('has_case_deduplication')),

    # User & Security Features
    MetricDef('mobile_user_groups', 'cp_n_mobile_user_groups',
              _not_implemented('mobile_user_groups'), is_boolean=False),
    MetricDef('has_user_case_management',
              'cp_has_user_case_management',
              _not_implemented('has_user_case_management')),
    MetricDef('has_organization', 'cp_has_organization',
              _not_implemented('has_organization')),
    MetricDef('user_profiles', 'cp_n_user_profiles',
              _not_implemented('user_profiles'), is_boolean=False),
    MetricDef('has_2fa_required', 'cp_has_2fa_required',
              _not_implemented('has_2fa_required')),
    MetricDef('has_shortened_timeout', 'cp_has_shortened_timeout',
              _not_implemented('has_shortened_timeout')),
    MetricDef('has_strong_passwords', 'cp_has_strong_passwords',
              _not_implemented('has_strong_passwords')),
    MetricDef('has_data_dictionary', 'cp_has_data_dictionary',
              _not_implemented('has_data_dictionary')),
    MetricDef('has_sso', 'cp_has_sso',
              _not_implemented('has_sso')),
    MetricDef('bulk_case_editing_sessions',
              'cp_n_bulk_case_editing_sessions',
              _not_implemented('bulk_case_editing_sessions'),
              is_boolean=False),
]
