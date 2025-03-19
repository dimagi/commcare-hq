from couchdbkit import ResourceNotFound
from django.utils.translation import gettext as _

from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.linked_domain.const import (
    DOMAIN_LEVEL_DATA_MODELS,
    FEATURE_FLAG_DATA_MODEL_TOGGLES,
    FEATURE_FLAG_DATA_MODELS,
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_FIXTURE,
    MODEL_KEYWORD,
    MODEL_REPORT,
    MODEL_UCR_EXPRESSION,
    MODEL_AUTO_UPDATE_RULE,
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
    UCRExpressionLinkDetail,
    UpdateRuleLinkDetail
)
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.linked_domain.util import server_to_user_time, is_keyword_linkable
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.models import ReportConfiguration, UCRExpression
from corehq.apps.userreports.util import get_existing_reports


def build_domain_link_view_model(link, timezone):
    return {
        'downstream_domain': link.linked_domain,
        'upstream_domain': link.master_domain,
        'upstream_url': link.upstream_url,
        'downstream_url': link.downstream_url,
        'is_remote': link.is_remote,
        'last_update': server_to_user_time(link.last_pull, timezone) if link.last_pull else _('Never'),
        'has_full_access': link.has_full_access(),
    }


def get_upstream_and_downstream_apps(domain):
    """
    Return 2 lists of app_briefs
    The upstream_list contains apps that originated in the specified domain
    The downstream_list contains apps that have been pulled from a domain upstream of the specified domain
    """
    upstream_list = {}
    downstream_list = {}
    briefs = get_brief_apps_in_domain(domain, include_remote=False)
    for brief in briefs:
        if is_linked_app(brief):
            downstream_list[brief._id] = brief
        else:
            upstream_list[brief._id] = brief
    return upstream_list, downstream_list


def get_upstream_and_downstream_fixtures(domain, upstream_link):
    """
    Return 2 lists of fixtures
    The upstream_list contains fixtures that originated in the specified domain
    The downstream_list contains fixtures that have been pulled from a domain upstream of the specified domain
    """
    upstream_list = get_fixtures_for_domain(domain)
    downstream_list = get_fixtures_for_domain(upstream_link.master_domain) if upstream_link else {}
    return upstream_list, downstream_list


def get_fixtures_for_domain(domain):
    fixtures = LookupTable.objects.filter(domain=domain, is_global=True)
    return {f.tag: f for f in fixtures}


def get_rules_for_domain(domain):
    rules = AutomaticUpdateRule.by_domain(domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, active_only=False)
    return {rule.id: rule for rule in rules}


def get_upstream_and_downstream_reports(domain):
    """
    Return 2 lists of reports
    The upstream_list contains reports that originated in the specified domain
    The downstream_list contains reports that have been pulled from a domain upstream of the specified domain
    """
    upstream_list = {}
    downstream_list = {}
    reports = get_existing_reports(domain)
    for report in reports:
        if report.report_meta.master_id:
            downstream_list[report.get_id] = report
        else:
            upstream_list[report.get_id] = report
    return upstream_list, downstream_list


def get_upstream_and_downstream_keywords(domain):
    """
    Return 2 lists of keywords
    The upstream_list contains keywords that originated in the specified domain
    The downstream_list contains keywords that have been pulled from a domain upstream of the specified domain
    """
    upstream_list = {}
    downstream_list = {}
    keywords = Keyword.objects.filter(domain=domain)
    for keyword in keywords:
        if keyword.upstream_id:
            downstream_list[str(keyword.id)] = keyword
        else:
            upstream_list[str(keyword.id)] = keyword
    return upstream_list, downstream_list


def get_upstream_and_downstream_ucr_expressions(domain):
    """
    Return 2 lists of ucr expressions
    The upstream_list contains ucr expressions that originated in the specified domain
    The downstream_list contains ucr expressions that have been pulled from a domain
    upstream of the specified domain
    """
    upstream_list = {}
    downstream_list = {}
    ucr_expressions = UCRExpression.objects.filter(domain=domain)
    for ucr_expression in ucr_expressions:
        if ucr_expression.upstream_id:
            downstream_list[str(ucr_expression.id)] = ucr_expression
        else:
            upstream_list[str(ucr_expression.id)] = ucr_expression
    return upstream_list, downstream_list


def get_upstream_and_downstream_update_rules(domain, upstream_link):
    upstream_rules = get_rules_for_domain(domain)
    downstream_rules = get_rules_for_domain(upstream_link.master_domain) if upstream_link else {}
    return upstream_rules, downstream_rules


def build_app_view_model(app, last_update=None):
    if not app:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_APP,
        name=f"{LINKED_MODELS_MAP[MODEL_APP]} ({app.name})",
        detail=AppLinkDetail(app_id=app._id).to_json(),
        last_update=last_update,
    )


def build_fixture_view_model(fixture, last_update=None):
    if not fixture:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_FIXTURE,
        name=f"{LINKED_MODELS_MAP[MODEL_FIXTURE]} ({fixture.tag})",
        detail=FixtureLinkDetail(tag=fixture.tag).to_json(),
        last_update=last_update,
        can_update=fixture.is_global,
    )


def build_update_rule_model(rule, last_update=None):
    if not rule:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_AUTO_UPDATE_RULE,
        name=f"Update Rule ({rule.name})",
        detail=UpdateRuleLinkDetail(id=rule.id).to_json(),
        last_update=last_update
    )


def build_report_view_model(report, last_update=None):
    if not report:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_REPORT,
        name=f"{LINKED_MODELS_MAP[MODEL_REPORT]} ({report.title})",
        detail=ReportLinkDetail(report_id=report.get_id).to_json(),
        last_update=last_update,
    )


def build_keyword_view_model(keyword, last_update=None):
    if not keyword:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_KEYWORD,
        name=f"{LINKED_MODELS_MAP[MODEL_KEYWORD]} ({keyword.keyword})",
        detail=KeywordLinkDetail(keyword_id=str(keyword.id)).to_json(),
        last_update=last_update,
        is_linkable=is_keyword_linkable(keyword),
    )


def build_ucr_expression_view_model(ucr_expression, last_update=None):
    if not ucr_expression:
        return None

    return build_linked_data_view_model(
        model_type=MODEL_UCR_EXPRESSION,
        name=f"{LINKED_MODELS_MAP[MODEL_UCR_EXPRESSION]} ({ucr_expression.name})",
        detail=UCRExpressionLinkDetail(ucr_expression_id=str(ucr_expression.id)).to_json(),
        last_update=last_update,
    )


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


def build_linked_data_view_model(model_type, name, detail,
        last_update=None, can_update=True, is_linkable=True):
    return {
        'type': model_type,
        'name': name,
        'detail': detail,
        'last_update': last_update,
        'can_update': can_update,
        'is_linkable': is_linkable,
    }


def build_view_models_from_data_models(
    domain, apps, fixtures, reports, keywords, ucr_expressions, update_rules,
    ignore_models=None, is_superuser=False
):
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

    for ucr_expression in ucr_expressions.values():
        ucr_expression_view_model = build_ucr_expression_view_model(ucr_expression)
        if ucr_expression_view_model:
            view_models.append(ucr_expression_view_model)

    for update_rule in update_rules.values():
        update_rule_view_model = build_update_rule_model(update_rule)
        if update_rule_view_model:
            view_models.append(update_rule_view_model)

    return view_models


def pop_app(app_id, apps):
    return apps.pop(app_id, None)


def pop_fixture(fixture_id, fixtures, domain):
    fixture = fixtures.pop(fixture_id, None)
    if not fixture:
        try:
            fixture = LookupTable.objects.by_domain_tag(domain, fixture_id)
        except LookupTable.DoesNotExist:
            fixture = None

    return fixture


def pop_report(report_id, reports):
    report = reports.pop(report_id, None)
    if report is None:
        try:
            report = ReportConfiguration.get(report_id)
        except ResourceNotFound:
            return None

        if report.doc_type == "ReportConfiguration-Deleted":
            report = None
    return report


def pop_update_rule(rule_id, rules):
    rule = rules.pop(rule_id, None)
    if rule is None:
        try:
            rule = AutomaticUpdateRule.objects.get(id=rule_id)
        except AutomaticUpdateRule.DoesNotExist:
            rule = None
    return rule


def pop_keyword(keyword_id, keywords):
    keyword = keywords.pop(keyword_id, None)
    if keyword is None:
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            keyword = None
    return keyword


def pop_ucr_expression(ucr_expression_id, ucr_expressions):
    ucr_expression = ucr_expressions.pop(ucr_expression_id, None)
    if ucr_expression is None:
        try:
            ucr_expression = UCRExpression.objects.get(id=ucr_expression_id)
        except UCRExpression.DoesNotExist:
            ucr_expression = None
    return ucr_expression


def build_pullable_view_models_from_data_models(
    domain, upstream_link, apps, fixtures, reports, keywords, ucr_expressions, update_rules,
    timezone, is_superuser=False
):
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
            app_id = action.wrapped_detail.app_id if action.model_detail else None
            app = pop_app(app_id, apps)
            view_model = build_app_view_model(app, last_update=last_update)
        elif action.model == MODEL_FIXTURE:
            fixture_id = action.wrapped_detail.tag if action.model_detail else None
            fixture = pop_fixture(fixture_id, fixtures, domain)
            view_model = build_fixture_view_model(fixture, last_update=last_update)
        elif action.model == MODEL_REPORT:
            report = pop_report(action.wrapped_detail.report_id, reports)
            view_model = build_report_view_model(report, last_update=last_update)
        elif action.model == MODEL_KEYWORD:
            keyword = pop_keyword(action.wrapped_detail.keyword_id, keywords)
            view_model = build_keyword_view_model(keyword, last_update=last_update)
        elif action.model == MODEL_UCR_EXPRESSION:
            ucr_expression = pop_ucr_expression(action.wrapped_detail.ucr_expression_id, ucr_expressions)
            view_model = build_ucr_expression_view_model(ucr_expression, last_update=last_update)
        elif action.model == MODEL_AUTO_UPDATE_RULE:
            rule = pop_update_rule(action.wrapped_detail.id, update_rules)
            view_model = build_update_rule_model(rule, last_update=last_update)
        else:
            # I would like to grab the last time that all automatic update rules were updated,
            # and use that as a fallback for when individual update rules were last updated,
            # but that would require knowing what rules were present when the group was updated,
            # which the present code doesn't support
            view_model = build_linked_data_view_model(
                model_type=action.model,
                name=LINKED_MODELS_MAP[action.model],
                detail=action.model_detail,
                last_update=last_update,
            )
        if view_model:
            if view_model['type'] not in dict(SUPERUSER_DATA_MODELS).keys() or is_superuser:
                linked_data_view_models.append(view_model)

    # Add data models that have never been pulled into the downstream domain before
    # ignoring any models we have already added via domain history
    linked_data_view_models.extend(
        build_view_models_from_data_models(
            domain,
            apps,
            fixtures,
            reports,
            keywords,
            ucr_expressions,
            update_rules,
            ignore_models=models_seen,
            is_superuser=is_superuser
        )
    )

    return linked_data_view_models
