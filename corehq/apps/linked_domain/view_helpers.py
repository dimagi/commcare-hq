from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_type_by_tag,
    get_fixture_data_types,
)
from corehq.apps.linked_domain.const import (
    DOMAIN_LEVEL_DATA_MODELS,
    FEATURE_FLAG_DATA_MODEL_TOGGLES,
    FEATURE_FLAG_DATA_MODELS,
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_FIXTURE,
    MODEL_FLAGS,
    MODEL_KEYWORD,
    MODEL_REPORT,
    SUPERUSER_DATA_MODELS,
)
from corehq.apps.linked_domain.dbaccessors import (
    get_actions_in_domain_link_history,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    FixtureLinkDetail,
    KeywordLinkDetail,
    ReportLinkDetail,
)
from corehq.apps.linked_domain.util import server_to_user_time
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import ReportConfiguration


def get_apps(domain):
    master_list = {}
    linked_list = {}
    briefs = get_brief_apps_in_domain(domain, include_remote=False)
    for brief in briefs:
        if is_linked_app(brief):
            linked_list[brief._id] = brief
        else:
            master_list[brief._id] = brief
    return master_list, linked_list


def get_fixtures(domain, master_link):
    master_list = get_fixtures_for_domain(domain)
    linked_list = get_fixtures_for_domain(master_link.master_domain) if master_link else {}
    return master_list, linked_list


def get_fixtures_for_domain(domain):
    fixtures = get_fixture_data_types(domain)
    return {f.tag: f for f in fixtures if f.is_global}


def get_reports(domain):
    master_list = {}
    linked_list = {}
    reports = get_report_configs_for_domain(domain)
    for report in reports:
        if report.report_meta.master_id:
            linked_list[report.get_id] = report
        else:
            master_list[report.get_id] = report
    return master_list, linked_list


def get_keywords(domain):
    master_list = {}
    linked_list = {}
    keywords = Keyword.objects.filter(domain=domain)
    for keyword in keywords:
        if keyword.upstream_id:
            linked_list[str(keyword.id)] = keyword
        else:
            master_list[str(keyword.id)] = keyword
    return master_list, linked_list


def build_app_view_model(app, last_update=None):
    can_update = False
    name = _('Unknown App')
    detail = None

    if app:
        can_update = True
        name = app.name
        detail = AppLinkDetail(app_id=app._id).to_json()

    view_model = build_linked_data_view_model(
        model_type=MODEL_APP,
        name=f"{LINKED_MODELS_MAP[MODEL_APP]} ({name})",
        detail=detail,
        last_update=last_update,
        can_update=can_update
    )

    return view_model


def build_fixture_view_model(fixture, last_update=None):
    can_update = False
    name = _('Unknown Table')
    detail = None

    if fixture:
        can_update = fixture.is_global
        name = fixture.tag
        detail = FixtureLinkDetail(tag=fixture.tag).to_json()

    view_model = build_linked_data_view_model(
        model_type=MODEL_FIXTURE,
        name=f"{LINKED_MODELS_MAP[MODEL_FIXTURE]} ({name})",
        detail=detail,
        last_update=last_update,
        can_update=can_update
    )

    return view_model


def build_report_view_model(report, last_update=None):
    can_update = False
    name = _("Unknown Report")
    detail = None

    if report:
        can_update = True
        name = report.title
        detail = ReportLinkDetail(report_id=report.get_id).to_json()

    view_model = build_linked_data_view_model(
        model_type=MODEL_REPORT,
        name=f"{LINKED_MODELS_MAP[MODEL_REPORT]} ({name})",
        detail=detail,
        last_update=last_update,
        can_update=can_update
    )

    return view_model


def build_keyword_view_model(keyword, last_update=None):
    can_update = False
    name = _("Deleted Keyword")
    detail = None

    if keyword:
        can_update = True
        name = keyword.keyword
        detail = KeywordLinkDetail(keyword_id=str(keyword.id)).to_json()

    view_model = build_linked_data_view_model(
        model_type=MODEL_KEYWORD,
        name=f"{LINKED_MODELS_MAP[MODEL_KEYWORD]} ({name})",
        detail=detail,
        last_update=last_update,
        can_update=can_update
    )

    return view_model


def build_feature_flag_view_models(domain, ignore_models=None):
    ignore_models = ignore_models or []
    view_models = []

    for model, name in FEATURE_FLAG_DATA_MODELS:
        if model not in ignore_models and FEATURE_FLAG_DATA_MODEL_TOGGLES[model].enabled(domain):
            view_models.append(
                build_linked_data_view_model(
                    model_type=model,
                    name=name,
                    detail=None,
                    last_update=_('Never')
                )
            )

    return view_models


def build_domain_level_view_models(ignore_models=None):
    ignore_models = ignore_models or []
    view_models = []

    for model, name in DOMAIN_LEVEL_DATA_MODELS:
        if model not in ignore_models:
            view_models.append(
                build_linked_data_view_model(
                    model_type=model,
                    name=name,
                    detail=None,
                    last_update=_('Never')
                )
            )

    return view_models


def build_superuser_view_models(ignore_models=None):
    ignore_models = ignore_models or []
    view_models = []

    for model, name in SUPERUSER_DATA_MODELS:
        if model not in ignore_models:
            view_models.append(
                build_linked_data_view_model(
                    model_type=model,
                    name=name,
                    detail=None,
                    last_update=_('Never')
                )
            )

    return view_models


def build_linked_data_view_model(model_type, name, detail, last_update=None, can_update=True):
    return {
        'type': model_type,
        'name': name,
        'detail': detail,
        'last_update': last_update,
        'can_update': can_update
    }


def build_view_models_from_data_models(domain, apps, fixtures, reports, keywords, ignore_models=None,
                                       is_superuser=False):
    """
    Based on the provided data models, convert to view models, ignoring any models specified in ignore_models
    :return: list of view models (dicts) used to render elements on the release content page
    """
    view_models = []

    if is_superuser:
        superuser_view_models = build_superuser_view_models(ignore_models=ignore_models)
        view_models.extend(superuser_view_models)

    domain_level_view_models = build_domain_level_view_models(ignore_models=ignore_models)
    view_models.extend(domain_level_view_models)

    feature_flag_view_models = build_feature_flag_view_models(domain, ignore_models=ignore_models)
    view_models.extend(feature_flag_view_models)

    for app in apps.values():
        app_view_model = build_app_view_model(app)
        if app_view_model:
            view_models.append(app_view_model)

    for fixture in fixtures.values():
        fixture_view_model = build_fixture_view_model(fixture)
        if fixture_view_model:
            view_models.append(fixture_view_model)

    for report in reports.values():
        report_view_model = build_report_view_model(report)
        if report_view_model:
            view_models.append(report_view_model)

    for keyword in keywords.values():
        keyword_view_model = build_keyword_view_model(keyword)
        if keyword_view_model:
            view_models.append(keyword_view_model)

    return view_models


def pop_app_for_action(action, apps):
    app = None
    if action.model_detail:
        app_id = action.wrapped_detail.app_id
        app = apps.pop(app_id, None)

    return app


def pop_fixture_for_action(action, fixtures, domain):
    fixture = None
    if action.model_detail:
        tag = action.wrapped_detail.tag
        fixture = fixtures.pop(tag, None)
        if not fixture:
            fixture = get_fixture_data_type_by_tag(domain, tag)

    return fixture


def pop_report_for_action(action, reports):
    report_id = action.wrapped_detail.report_id
    try:
        report = reports.get(report_id)
        del reports[report_id]
    except KeyError:
        report = ReportConfiguration.get(report_id)

    return report


def pop_keyword_for_action(action, keywords):
    keyword_id = action.wrapped_detail.keyword_id
    try:
        keyword = keywords[keyword_id]
        del keywords[keyword_id]
    except KeyError:
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            keyword = None

    return keyword


def build_pullable_view_models_from_data_models(domain, upstream_link, apps, fixtures, reports, keywords,
                                                timezone, is_superuser=False):
    """
    Data models that originated in this domain's upstream domain that are available to pull
    :return: list of view models (dicts) used to render linked data models that can be pulled
    """
    linked_data_view_models = []

    if not upstream_link:
        return linked_data_view_models

    models_seen = set()
    history = get_actions_in_domain_link_history(upstream_link)
    for action in history:
        if action.row_number != 1:
            # first row is the most recent
            continue

        models_seen.add(action.model)
        last_update = server_to_user_time(action.date, timezone)

        if action.model == MODEL_APP:
            app = pop_app_for_action(action, apps)
            view_model = build_app_view_model(app, last_update=last_update)
        elif action.model == MODEL_FIXTURE:
            fixture = pop_fixture_for_action(action, fixtures, domain)
            view_model = build_fixture_view_model(fixture, last_update=last_update)
        elif action.model == MODEL_REPORT:
            report = pop_report_for_action(action, reports)
            view_model = build_report_view_model(report, last_update=last_update)
        elif action.model == MODEL_KEYWORD:
            keyword = pop_keyword_for_action(action, keywords)
            view_model = build_keyword_view_model(keyword, last_update=last_update)
        else:
            view_model = build_linked_data_view_model(
                model_type=action.model,
                name=LINKED_MODELS_MAP[action.model],
                detail=action.model_detail,
                last_update=last_update,
            )

        if view_model['type'] not in dict(SUPERUSER_DATA_MODELS).keys() or is_superuser:
            linked_data_view_models.append(view_model)

    # Add data models that have never been pulled into the downstream domain before
    # ignoring any models we have already added via domain history
    linked_data_view_models.extend(
        build_view_models_from_data_models(
            domain, apps, fixtures, reports, keywords, ignore_models=models_seen, is_superuser=is_superuser)
    )

    return linked_data_view_models
