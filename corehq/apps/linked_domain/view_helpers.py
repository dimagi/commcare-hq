from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_type_by_tag,
    get_fixture_data_types,
)
from corehq.apps.linked_domain.const import (
    LINKED_MODELS,
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_FIXTURE,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_KEYWORD,
    MODEL_OTP_SETTINGS,
    MODEL_REPORT,
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
from corehq.util.timezones.utils import get_timezone_for_request


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
        name = keyword.keyword
        detail = KeywordLinkDetail(keyword_id=str(keyword.id)).to_json()
        can_update = True

    view_model = build_linked_data_view_model(
        model_type=MODEL_KEYWORD,
        name=f"{LINKED_MODELS_MAP[MODEL_KEYWORD]} ({name})",
        detail=detail,
        last_update=last_update,
        can_update=can_update
    )

    return view_model


def build_other_view_models(domain, ignore_models=None):
    ignore_models = ignore_models or []
    view_models = []

    for model, name in LINKED_MODELS:
        if (
            model not in ignore_models
            and model not in (MODEL_APP, MODEL_FIXTURE, MODEL_REPORT, MODEL_KEYWORD)
            and (model != MODEL_CASE_SEARCH or toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain))
            and (model != MODEL_DATA_DICTIONARY or toggles.DATA_DICTIONARY.enabled(domain))
            and (model != MODEL_DIALER_SETTINGS or toggles.WIDGET_DIALER.enabled(domain))
            and (model != MODEL_OTP_SETTINGS or toggles.GAEN_OTP_SERVER.enabled(domain))
            and (model != MODEL_HMAC_CALLOUT_SETTINGS or toggles.HMAC_CALLOUT.enabled(domain))
        ):
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


def build_view_models_from_data_models(domain, apps, fixtures, reports, keywords, ignore_models=None):
    """
    Based on the provided data models, build generic
    :return: list of view models (dicts) used to render elements on the release content page
    """
    view_models = []

    other_view_models = build_other_view_models(domain, ignore_models=ignore_models)
    view_models.extend(other_view_models)

    for app in apps:
        app_view_model = build_app_view_model(app)
        if app_view_model:
            view_models.append(app_view_model)

    for fixture in fixtures:
        fixture_view_model = build_fixture_view_model(fixture)
        if fixture_view_model:
            view_models.append(fixture_view_model)

    for report in reports:
        report_view_model = build_report_view_model(report)
        if report_view_model:
            view_models.append(report_view_model)

    for keyword in keywords:
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
    keyword_id = action.wrapped_detail.linked_keyword_id
    try:
        keyword = keywords[keyword_id]
        del keywords[keyword_id]
    except KeyError:
        keyword = Keyword.objects.get(id=keyword_id)

    return keyword


def build_pullable_view_models_from_data_models(domain, upstream_link, apps, fixtures, reports, keywords):
    """
    Data models that originated in this domain's upstream domain that are available to pull
    :return: list of view models (dicts) used to render linked data models that can be pulled
    """
    linked_data_view_models = []

    if not upstream_link:
        return linked_data_view_models

    models_seen = set()
    timezone = get_timezone_for_request()
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

        linked_data_view_models.append(view_model)

    # Add data models that have never been pulled into the downstream domain before
    # ignoring any models we have already added via domain history
    linked_data_view_models.extend(
        build_view_models_from_data_models(
            domain, apps, fixtures, reports, keywords, ignore_models=models_seen)
    )

    return linked_data_view_models
