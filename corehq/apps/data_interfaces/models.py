import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models, transaction
from django.db.models import Q

import jsonfield
import pytz
from dateutil.parser import parse
from jsonobject.api import JsonObject
from jsonobject.properties import (
    BooleanProperty,
    IntegerProperty,
    StringProperty,
)
from memoized import memoized

from casexml.apps.case.xform import get_case_updates
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function

from corehq.apps.app_manager.dbaccessors import get_latest_released_app
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.models import AdvancedForm
from corehq.apps.data_interfaces.deduplication import find_duplicate_case_ids
from corehq.apps.data_interfaces.utils import property_references_parent
from corehq.apps.es.cases import CaseES
from corehq.apps.hqcase.utils import bulk_update_cases, update_case
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.abstract_models import DEFAULT_PARENT_IDENTIFIER
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.models import CommCareCaseIndexSQL, CommCareCaseSQL
from corehq.messaging.scheduling.const import (
    VISIT_WINDOW_DUE_DATE,
    VISIT_WINDOW_END,
    VISIT_WINDOW_START,
)
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_case_alert_schedule_instances_for_schedule_id,
    get_case_timed_schedule_instances_for_schedule_id,
)
from corehq.messaging.scheduling.tasks import (
    delete_case_alert_schedule_instances,
    delete_case_timed_schedule_instances,
    refresh_case_alert_schedule_instances,
    refresh_case_timed_schedule_instances,
)
from corehq.sql_db.util import (
    get_db_aliases_for_partitioned_query,
    paginate_query,
    paginate_query_across_partitioned_databases,
)
from corehq.util.log import with_progress_bar
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only

ALLOWED_DATE_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}')
AUTO_UPDATE_XMLNS = 'http://commcarehq.org/hq_case_update_rule'
DEDUPE_XMLNS = 'http://commcarehq.org/hq_case_deduplication_rule'


def _try_date_conversion(date_or_string):
    if isinstance(date_or_string, bytes):
        date_or_string = date_or_string.decode('utf-8')
    if isinstance(date_or_string, str) and ALLOWED_DATE_REGEX.match(date_or_string):
        try:
            return parse(date_or_string)
        except ValueError:
            pass
    return date_or_string


class AutomaticUpdateRule(models.Model):
    # Used when the rule performs case update actions
    WORKFLOW_CASE_UPDATE = 'CASE_UPDATE'

    # Used when the rule spawns schedule instances in the scheduling framework
    WORKFLOW_SCHEDULING = 'SCHEDULING'

    # Used when the rule runs a deduplication workflow to find duplicate cases
    WORKFLOW_DEDUPLICATE = 'DEDUPLICATE'

    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=126)
    case_type = models.CharField(max_length=126)
    active = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    last_run = models.DateTimeField(null=True)
    filter_on_server_modified = models.BooleanField(default=True)

    # For performance reasons, the server_modified_boundary is a
    # required part of the criteria and should be set to the minimum
    # number of days old that a case's server_modified_on date must be
    # before we run the rule against it.
    server_modified_boundary = models.IntegerField(null=True)

    # One of the WORKFLOW_* constants on this class describing the workflow
    # that this rule belongs to.
    workflow = models.CharField(max_length=126)

    locked_for_editing = models.BooleanField(default=False)

    class Meta(object):
        app_label = "data_interfaces"

    class MigrationError(Exception):
        pass

    class RuleError(Exception):
        pass

    def __str__(self):
        return f"rule: '{self.name}', id: {self.id}, domain: {self.domain}"

    @property
    def references_parent_case(self):
        for criterion in self.memoized_criteria:
            definition = criterion.definition
            if isinstance(definition, ClosedParentDefinition):
                return True
            elif (
                isinstance(definition, MatchPropertyDefinition) and
                property_references_parent(definition.property_name)
            ):
                return True

        for action in self.memoized_actions:
            definition = action.definition
            if isinstance(definition, UpdateCaseDefinition):
                for property_definition in definition.get_properties_to_update():
                    if property_references_parent(property_definition.name):
                        return True
                    if (
                        property_definition.value_type == UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY and
                        property_references_parent(property_definition.value)
                    ):
                        return True
            elif isinstance(definition, CreateScheduleInstanceActionDefinition):
                if (
                    property_references_parent(definition.reset_case_property_name) or
                    property_references_parent(definition.start_date_case_property)
                ):
                    return True

        return False

    @classmethod
    def by_domain(cls, domain, workflow, active_only=True):
        additional_filters = {}
        if active_only:
            additional_filters['active'] = True

        return cls.objects.filter(
            domain=domain,
            workflow=workflow,
            deleted=False,
            **additional_filters
        )

    @classmethod
    def domain_has_conditional_alerts(cls, domain):
        return cls.by_domain(domain, cls.WORKFLOW_SCHEDULING, active_only=False).exists()

    @classmethod
    @quickcache(['domain', 'workflow', 'active_only'], timeout=30 * 60)
    def by_domain_cached(cls, domain, workflow, active_only=True):
        result = cls.by_domain(domain, workflow, active_only=active_only)
        result = list(result)

        for rule in result:
            # Make the criteria and actions be memoized in the cached result
            rule.memoized_criteria
            rule.memoized_actions

        return result

    @classmethod
    def organize_rules_by_case_type(cls, rules):
        rules_by_case_type = {}
        for rule in rules:
            if rule.case_type not in rules_by_case_type:
                rules_by_case_type[rule.case_type] = [rule]
            else:
                rules_by_case_type[rule.case_type].append(rule)
        return rules_by_case_type

    # returns None if any of the rules do not filter on server modified
    @classmethod
    def get_boundary_date(cls, rules, now):
        min_boundary = None
        for rule in rules:
            if not rule.filter_on_server_modified:
                return None
            elif not min_boundary:
                min_boundary = rule.server_modified_boundary
            elif rule.server_modified_boundary < min_boundary:
                min_boundary = rule.server_modified_boundary
        date = now - timedelta(days=min_boundary)
        return date

    @classmethod
    def iter_cases(cls, domain, case_type, boundary_date=None, db=None):
        return cls._iter_cases_from_postgres(domain, case_type, boundary_date=boundary_date, db=db)

    @classmethod
    def _iter_cases_from_postgres(cls, domain, case_type, boundary_date=None, db=None):
        q_expression = Q(
            domain=domain,
            type=case_type,
            closed=False,
            deleted=False,
        )

        if boundary_date:
            q_expression = q_expression & Q(server_modified_on__lte=boundary_date)

        if db:
            return paginate_query(db, CommCareCaseSQL, q_expression, load_source='auto_update_rule')
        else:
            return paginate_query_across_partitioned_databases(
                CommCareCaseSQL, q_expression, load_source='auto_update_rule'
            )

    @classmethod
    def _iter_cases_from_es(cls, domain, case_type, boundary_date=None):
        case_ids = list(cls._get_case_ids_from_es(domain, case_type, boundary_date))
        return CaseAccessors(domain).iter_cases(case_ids)

    @classmethod
    def _get_case_ids_from_es(cls, domain, case_type, boundary_date=None):
        query = (CaseES()
                 .domain(domain)
                 .case_type(case_type)
                 .is_closed(closed=False)
                 .exclude_source()
                 .size(100))

        if boundary_date:
            query = query.server_modified_range(lte=boundary_date)

        for case_id in query.scroll():
            if not isinstance(case_id, str):
                raise ValueError("Something is wrong with the query, expected ids only")

            yield case_id

    def activate(self, active=True):
        self.active = active
        self.save()

    def soft_delete(self):
        with transaction.atomic():
            self.deleted = True
            self.save()
            if self.workflow == self.WORKFLOW_SCHEDULING:
                schedule = self.get_schedule()
                schedule.deleted = True
                schedule.save()
                if isinstance(schedule, AlertSchedule):
                    delete_case_alert_schedule_instances.delay(schedule.schedule_id)
                elif isinstance(schedule, TimedSchedule):
                    delete_case_timed_schedule_instances.delay(schedule.schedule_id)
                else:
                    raise TypeError("Unexpected schedule type")

    @unit_testing_only
    def hard_delete(self):
        self.delete_criteria()
        self.delete_actions()
        CaseRuleSubmission.objects.filter(rule=self).delete()
        self.delete()

    @property
    @memoized
    def memoized_criteria(self):
        return list(self.caserulecriteria_set.all().select_related(
            'match_property_definition',
            'custom_match_definition',
            'closed_parent_definition',
        ))

    @property
    @memoized
    def memoized_actions(self):
        return list(self.caseruleaction_set.all().select_related(
            'update_case_definition',
            'custom_action_definition',
            'create_schedule_instance_definition',
            'case_deduplication_action_definition',
        ))

    def run_rule(self, case, now):
        """
        :return: CaseRuleActionResult object aggregating the results from all actions.
        """
        if self.deleted:
            raise self.RuleError("Attempted to call run_rule on a deleted rule")

        if not self.active:
            raise self.RuleError("Attempted to call run_rule on an inactive rule")

        if not isinstance(case, CommCareCaseSQL) or case.domain != self.domain:
            raise self.RuleError("Invalid case given")

        if self.criteria_match(case, now):
            return self.run_actions_when_case_matches(case)
        else:
            return self.run_actions_when_case_does_not_match(case)

    def criteria_match(self, case, now):
        if case.is_deleted or case.closed:
            return False

        if case.type != self.case_type:
            return False

        if self.filter_on_server_modified and \
                (case.server_modified_on > (now - timedelta(days=self.server_modified_boundary))):
            return False

        if (self.workflow == AutomaticUpdateRule.WORKFLOW_DEDUPLICATE
                and self.last_run
                and not case.server_modified_on >= self.last_run):
            return False

        for criteria in self.memoized_criteria:
            try:
                result = criteria.definition.matches(case, now)
            except CaseNotFound:
                # This might happen if the criteria references a parent case and the
                # parent case is not found
                result = False

            if not result:
                return False

        return True

    def _run_method_on_action_definitions(self, case, method):
        aggregated_result = CaseRuleActionResult()

        for action in self.memoized_actions:
            callable_method = getattr(action.definition, method)
            result = callable_method(case, self)
            if not isinstance(result, CaseRuleActionResult):
                raise TypeError("Expected CaseRuleActionResult")

            aggregated_result.add_result(result)

        return aggregated_result

    def run_actions_when_case_matches(self, case):
        return self._run_method_on_action_definitions(case, 'when_case_matches')

    def run_actions_when_case_does_not_match(self, case):
        return self._run_method_on_action_definitions(case, 'when_case_does_not_match')

    def delete_criteria(self):
        for item in self.caserulecriteria_set.all():
            item.definition.delete()

        self.caserulecriteria_set.all().delete()

    def delete_actions(self):
        for item in self.caseruleaction_set.all():
            item.definition.delete()

        self.caseruleaction_set.all().delete()

    def log_submission(self, form_id):
        CaseRuleSubmission.objects.create(
            domain=self.domain,
            rule=self,
            created_on=datetime.utcnow(),
            form_id=form_id,
        )

    def add_criteria(self, definition_class, **definition_kwargs):
        criteria = CaseRuleCriteria(rule=self)
        definition = definition_class.objects.create(**definition_kwargs)
        criteria.definition = definition
        criteria.save()
        return criteria, definition

    def add_action(self, definition_class, **definition_kwargs):
        action = CaseRuleAction(rule=self)
        definition = definition_class.objects.create(**definition_kwargs)
        action.definition = definition
        action.save()
        return action, definition

    def save(self, *args, **kwargs):
        super(AutomaticUpdateRule, self).save(*args, **kwargs)
        # If we're in a transaction.atomic() block, this gets executed after commit
        # If we're not, this gets executed right away
        transaction.on_commit(lambda: self.clear_caches(self.domain, self.workflow))

    @classmethod
    def clear_caches(cls, domain, workflow):
        # domain and workflow should never change once set
        for active_only in (True, False):
            cls.by_domain_cached.clear(
                AutomaticUpdateRule,
                domain,
                workflow,
                active_only=active_only,
            )

    def get_action_definition(self):
        if self.workflow != self.WORKFLOW_SCHEDULING:
            raise ValueError("Expected scheduling workflow")

        if len(self.memoized_actions) != 1:
            raise ValueError("Expected exactly 1 action")

        action = self.memoized_actions[0]
        action_definition = action.definition
        if not isinstance(action_definition, CreateScheduleInstanceActionDefinition):
            raise TypeError("Expected CreateScheduleInstanceActionDefinition")

        return action_definition

    def get_schedule(self):
        return self.get_action_definition().schedule


class CaseRuleCriteria(models.Model):
    rule = models.ForeignKey('AutomaticUpdateRule', on_delete=models.PROTECT)
    match_property_definition = models.ForeignKey('MatchPropertyDefinition', on_delete=models.CASCADE, null=True)
    custom_match_definition = models.ForeignKey('CustomMatchDefinition', on_delete=models.CASCADE, null=True)
    closed_parent_definition = models.ForeignKey('ClosedParentDefinition', on_delete=models.CASCADE, null=True)

    @property
    def definition(self):
        if self.match_property_definition_id:
            return self.match_property_definition
        elif self.custom_match_definition_id:
            return self.custom_match_definition
        elif self.closed_parent_definition_id:
            return self.closed_parent_definition
        else:
            raise ValueError("No available definition found")

    @definition.setter
    def definition(self, value):
        self.match_property_definition = None
        self.custom_match_definition = None
        self.closed_parent_definition = None

        if isinstance(value, MatchPropertyDefinition):
            self.match_property_definition = value
        elif isinstance(value, CustomMatchDefinition):
            self.custom_match_definition = value
        elif isinstance(value, ClosedParentDefinition):
            self.closed_parent_definition = value
        else:
            raise ValueError("Unexpected type found: %s" % type(value))


class CaseRuleCriteriaDefinition(models.Model):

    class Meta(object):
        abstract = True

    def matches(self, case, now):
        raise NotImplementedError()


class MatchPropertyDefinition(CaseRuleCriteriaDefinition):
    # True when today < (the date in property_name + property_value days)
    MATCH_DAYS_BEFORE = 'DAYS_BEFORE'

    # True when today >= (the date in property_name + property_value days)
    MATCH_DAYS_AFTER = 'DAYS'

    MATCH_EQUAL = 'EQUAL'
    MATCH_NOT_EQUAL = 'NOT_EQUAL'
    MATCH_HAS_VALUE = 'HAS_VALUE'
    MATCH_HAS_NO_VALUE = 'HAS_NO_VALUE'
    MATCH_REGEX = 'REGEX'

    MATCH_CHOICES = (
        MATCH_DAYS_BEFORE,
        MATCH_DAYS_AFTER,
        MATCH_EQUAL,
        MATCH_NOT_EQUAL,
        MATCH_HAS_VALUE,
        MATCH_HAS_NO_VALUE,
        MATCH_REGEX,
    )

    property_name = models.CharField(max_length=126)
    property_value = models.CharField(max_length=126, null=True)
    match_type = models.CharField(max_length=15)

    def get_case_values(self, case):
        values = case.resolve_case_property(self.property_name)
        return [element.value for element in values]

    def clean_datetime(self, timestamp):
        if not isinstance(timestamp, datetime):
            timestamp = datetime.combine(timestamp, time(0, 0))

        if timestamp.tzinfo:
            # Convert to UTC and make it a naive datetime for comparison to datetime.utcnow()
            timestamp = timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        return timestamp

    def check_days_before(self, case, now):
        values = self.get_case_values(case)
        for date_to_check in values:
            date_to_check = _try_date_conversion(date_to_check)

            if not isinstance(date_to_check, date):
                continue

            date_to_check = self.clean_datetime(date_to_check)

            days = int(self.property_value)
            if now < (date_to_check + timedelta(days=days)):
                return True

        return False

    def check_days_after(self, case, now):
        values = self.get_case_values(case)
        for date_to_check in values:
            date_to_check = _try_date_conversion(date_to_check)

            if not isinstance(date_to_check, date):
                continue

            date_to_check = self.clean_datetime(date_to_check)

            days = int(self.property_value)
            if now >= (date_to_check + timedelta(days=days)):
                return True

        return False

    def check_equal(self, case, now):
        return any([
            value == self.property_value for value in self.get_case_values(case)
        ])

    def check_not_equal(self, case, now):
        return any([
            value != self.property_value for value in self.get_case_values(case)
        ])

    def check_has_value(self, case, now):
        values = self.get_case_values(case)
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return True

        return False

    def check_has_no_value(self, case, now):
        return not self.check_has_value(case, now)

    def check_regex(self, case, now):
        try:
            regex = re.compile(self.property_value)
        except (re.error, ValueError, TypeError):
            return False

        for value in self.get_case_values(case):
            if isinstance(value, str):
                try:
                    if regex.match(value):
                        return True
                except (re.error, ValueError, TypeError):
                    pass

        return False

    def matches(self, case, now):
        return {
            self.MATCH_DAYS_BEFORE: self.check_days_before,
            self.MATCH_DAYS_AFTER: self.check_days_after,
            self.MATCH_EQUAL: self.check_equal,
            self.MATCH_NOT_EQUAL: self.check_not_equal,
            self.MATCH_HAS_VALUE: self.check_has_value,
            self.MATCH_HAS_NO_VALUE: self.check_has_no_value,
            self.MATCH_REGEX: self.check_regex,
        }.get(self.match_type)(case, now)


class CustomMatchDefinition(CaseRuleCriteriaDefinition):
    name = models.CharField(max_length=126)

    def matches(self, case, now):
        if self.name not in settings.AVAILABLE_CUSTOM_RULE_CRITERIA:
            raise ValueError("%s not found in AVAILABLE_CUSTOM_RULE_CRITERIA" % self.name)

        custom_function_path = settings.AVAILABLE_CUSTOM_RULE_CRITERIA[self.name]
        try:
            custom_function = to_function(custom_function_path)
        except:
            raise ValueError("Unable to resolve '%s'" % custom_function_path)

        return custom_function(case, now)


class ClosedParentDefinition(CaseRuleCriteriaDefinition):
    # This matches up to the identifier attribute in a CommCareCaseIndex
    # (couch backend) or CommCareCaseIndexSQL (postgres backend) record.
    identifier = models.CharField(max_length=126, default=DEFAULT_PARENT_IDENTIFIER)

    # This matches up to the CommCareCaseIndexSQL.relationship_id field.
    # The framework will automatically convert it to the string used in
    # the CommCareCaseIndex (couch backend) model for domains that use
    # the couch backend.
    relationship_id = models.PositiveSmallIntegerField(default=CommCareCaseIndexSQL.CHILD)

    def matches(self, case, now):
        relationship = self.relationship_id

        for parent in case.get_parent(identifier=self.identifier, relationship=relationship):
            if parent.closed:
                return True

        return False


class CaseRuleAction(models.Model):
    rule = models.ForeignKey('AutomaticUpdateRule', on_delete=models.PROTECT)
    update_case_definition = models.ForeignKey('UpdateCaseDefinition', on_delete=models.CASCADE, null=True)
    custom_action_definition = models.ForeignKey('CustomActionDefinition', on_delete=models.CASCADE, null=True)
    create_schedule_instance_definition = models.ForeignKey('CreateScheduleInstanceActionDefinition',
        on_delete=models.CASCADE, null=True)
    case_deduplication_action_definition = models.ForeignKey('CaseDeduplicationActionDefinition',
                                                             on_delete=models.CASCADE, null=True)

    @property
    def definition(self):
        if self.update_case_definition_id:
            return self.update_case_definition
        elif self.custom_action_definition_id:
            return self.custom_action_definition
        elif self.create_schedule_instance_definition_id:
            return self.create_schedule_instance_definition
        elif self.case_deduplication_action_definition_id:
            return self.case_deduplication_action_definition
        else:
            raise ValueError("No available definition found")

    @definition.setter
    def definition(self, value):
        self.update_case_definition = None
        self.custom_action_definition = None
        self.create_schedule_instance_definition = None

        if isinstance(value, UpdateCaseDefinition):
            self.update_case_definition = value
        elif isinstance(value, CustomActionDefinition):
            self.custom_action_definition = value
        elif isinstance(value, CreateScheduleInstanceActionDefinition):
            self.create_schedule_instance_definition = value
        elif isinstance(value, CaseDeduplicationActionDefinition):
            self.case_deduplication_action_definition = value
        else:
            raise ValueError("Unexpected type found: %s" % type(value))


class CaseRuleActionResult(object):

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    __hash__ = None

    def _validate_int(self, value):
        if not isinstance(value, int):
            raise ValueError("Expected int")

    def __init__(self, num_updates=0, num_closes=0, num_related_updates=0, num_related_closes=0, num_creates=0):
        self._validate_int(num_updates)
        self._validate_int(num_closes)
        self._validate_int(num_related_updates)
        self._validate_int(num_related_closes)
        self._validate_int(num_creates)

        self.num_updates = num_updates
        self.num_closes = num_closes
        self.num_related_updates = num_related_updates
        self.num_related_closes = num_related_closes
        self.num_creates = num_creates

    def add_result(self, result):
        self.num_updates += result.num_updates
        self.num_closes += result.num_closes
        self.num_related_updates += result.num_related_updates
        self.num_related_closes += result.num_related_closes
        self.num_creates += result.num_creates

    @property
    def total_updates(self):
        return (
            self.num_updates +
            self.num_closes +
            self.num_related_updates +
            self.num_related_closes +
            self.num_creates
        )


class CaseRuleActionDefinition(models.Model):

    class Meta(object):
        abstract = True

    def when_case_matches(self, case, rule):
        """
        Defines the actions to be taken when the case matches the rule.
        Should return an instance of CaseRuleActionResult
        """
        raise NotImplementedError()

    def when_case_does_not_match(self, case, rule):
        """
        Defines the actions to be taken when the case does not match the rule.
        This method can be optionally overriden, but by default does nothing.
        Should return an instance of CaseRuleActionResult
        """
        return CaseRuleActionResult()


class BaseUpdateCaseDefinition(CaseRuleActionDefinition):
    class Meta(object):
        abstract = True

    # Expected to be a list of PropertyDefinition objects representing the
    # case properties to update
    properties_to_update = jsonfield.JSONField(default=list)

    VALUE_TYPE_EXACT = "EXACT"
    VALUE_TYPE_CASE_PROPERTY = "CASE_PROPERTY"

    VALUE_TYPE_CHOICES = (
        VALUE_TYPE_EXACT,
        VALUE_TYPE_CASE_PROPERTY,
    )

    class PropertyDefinition(JsonObject):
        # The case property name
        name = StringProperty()

        # The type of the value property:
        #   VALUE_TYPE_EXACT means `value` is the exact value to set to the case property referred to by `name`.
        #   VALUE_TYPE_CASE_PROPERTY means `value` is a case property to resolve first and then set to the case
        #   property referred to by `name`.
        value_type = StringProperty()

        # Meaning depends on value_type, see above
        value = StringProperty()

    def get_properties_to_update(self):
        return [self.PropertyDefinition(**fields) for fields in self.properties_to_update]

    def set_properties_to_update(self, properties):
        if not isinstance(properties, (list, tuple)):
            raise ValueError("Expected list or tuple")

        result = []
        for p in properties:
            if not isinstance(p, self.PropertyDefinition):
                raise ValueError("Expected {}.PropertyDefinition".format(self.__class__.__name__))

            result.append(p.to_json())

        self.properties_to_update = result

    def get_case_and_ancestor_updates(self, case):
        cases_to_update = defaultdict(dict)

        def _get_case_property_value(current_case, name):
            result = current_case.resolve_case_property(name)
            if result:
                return result[0].value

            return None

        def _add_update_property(name, value, current_case):
            while True:
                if name.lower().startswith('parent/'):
                    name = name[7:]
                    # uses first parent if there are multiple
                    parent_cases = current_case.get_parent(identifier=DEFAULT_PARENT_IDENTIFIER)
                    if parent_cases:
                        current_case = parent_cases[0]
                    else:
                        return
                elif name.lower().startswith('host/'):
                    name = name[5:]
                    current_case = current_case.host
                    if not current_case:
                        return
                else:
                    break

            cases_to_update[current_case.case_id][name] = value

        for prop in self.get_properties_to_update():
            if prop.value_type == self.VALUE_TYPE_CASE_PROPERTY:
                value = _get_case_property_value(case, prop.value)
                if value is None:
                    continue
            elif prop.value_type == self.VALUE_TYPE_EXACT:
                value = prop.value
            else:
                raise ValueError("Unexpected value_type found: %s" % prop.value_type)

            if value != _get_case_property_value(case, prop.name):
                _add_update_property(prop.name, value, case)

        return cases_to_update

    def get_cases_to_update(self):
        raise NotImplementedError()


class UpdateCaseDefinition(BaseUpdateCaseDefinition):
    # True to close the case, otherwise False
    close_case = models.BooleanField()

    def when_case_matches(self, case, rule):
        cases_to_update = self.get_case_and_ancestor_updates(case)

        num_updates = 0
        num_closes = 0
        num_related_updates = 0

        # Update any referenced parent cases
        for case_id, properties in cases_to_update.items():
            if case_id == case.case_id:
                continue
            result = update_case(case.domain, case_id, case_properties=properties, close=False,
                xmlns=AUTO_UPDATE_XMLNS)

            rule.log_submission(result[0].form_id)
            num_related_updates += 1

        # Update / close the case
        properties = cases_to_update[case.case_id]
        try:
            close_case = self.close_case
        except AttributeError:
            close_case = False

        if close_case or properties:
            result = update_case(case.domain, case.case_id, case_properties=properties, close=close_case,
                xmlns=AUTO_UPDATE_XMLNS)

            rule.log_submission(result[0].form_id)

            if properties:
                num_updates += 1

            if close_case:
                num_closes += 1

        return CaseRuleActionResult(
            num_updates=num_updates,
            num_closes=num_closes,
            num_related_updates=num_related_updates,
        )

class CustomActionDefinition(CaseRuleActionDefinition):
    name = models.CharField(max_length=126)

    def when_case_matches(self, case, rule):
        if self.name not in settings.AVAILABLE_CUSTOM_RULE_ACTIONS:
            raise ValueError("%s not found in AVAILABLE_CUSTOM_RULE_ACTIONS" % self.name)

        custom_function_path = settings.AVAILABLE_CUSTOM_RULE_ACTIONS[self.name]
        try:
            custom_function = to_function(custom_function_path)
        except:
            raise ValueError("Unable to resolve '%s'" % custom_function_path)

        return custom_function(case, rule)


class CaseDeduplicationMatchTypeChoices:
    ANY = "ANY"
    ALL = "ALL"
    CHOICES = (
        (ANY, ANY),
        (ALL, ALL),
    )


class CaseDeduplicationActionDefinition(BaseUpdateCaseDefinition):
    match_type = models.CharField(choices=CaseDeduplicationMatchTypeChoices.CHOICES, max_length=5)
    case_properties = ArrayField(models.TextField())
    include_closed = models.BooleanField(default=False)

    def properties_fit_definition(self, case_properties):
        """Given a list of case properties, returns whether these will be pertinent in
        finding duplicate cases.

        Used when deciding whether to run the action from the pillow.

        """

        definition_properties = set(self.case_properties)
        case_properties = set(case_properties)

        all_match = (
            self.match_type == CaseDeduplicationMatchTypeChoices.ALL
            and case_properties.issuperset(definition_properties)
        )

        any_match = (
            self.match_type == CaseDeduplicationMatchTypeChoices.ANY
            and case_properties.intersection(definition_properties)
        )

        return all_match or any_match

    def when_case_matches(self, case, rule):
        domain = case.domain
        new_duplicate_case_ids = set(find_duplicate_case_ids(
            domain, case, self.case_properties, self.include_closed, self.match_type
        ))
        # If the case being searched isn't in the case search index
        # (e.g. if this is a case create, and the pillows are racing each other.)
        # Add it to the list
        new_duplicate_case_ids.add(case.case_id)

        with transaction.atomic():
            if self._handle_existing_duplicates(case.case_id, new_duplicate_case_ids):
                return CaseRuleActionResult(num_updates=0)
            CaseDuplicate.bulk_create_duplicate_relationships(self, case, new_duplicate_case_ids)

        num_updates = self._update_cases(domain, rule, new_duplicate_case_ids)
        return CaseRuleActionResult(num_updates=num_updates)

    def _handle_existing_duplicates(self, case_id, new_duplicate_case_ids):
        """Handles existing duplicate objects.

        Returns True if there is nothing else to be done
        """
        try:
            existing_duplicate_case_ids = set(
                CaseDuplicate.objects
                .prefetch_related('potential_duplicates')
                .get(action=self, case_id=case_id)
                .potential_duplicates
                .all()
                .values_list('case_id', flat=True)
            ) | set([case_id])  # The duplicates we currently have for this case tracked in the system
        except CaseDuplicate.DoesNotExist:
            # There are no duplicate cases currently in the system.
            # We continue on to create duplicates only if there are duplicates to create.
            return new_duplicate_case_ids == {case_id}

        if new_duplicate_case_ids == {case_id}:
            # This is no longer a duplicate, so check that there aren't any
            # other cases that are no longer duplicates
            CaseDuplicate.remove_unique_cases(action=self, case_id=case_id)
            CaseDuplicate.objects.filter(action=self, case_id=case_id).delete()
            return True

        if new_duplicate_case_ids == existing_duplicate_case_ids:
            # If the list of duplicates hasn't changed, we don't need to do anything more
            return True

        # Delete all CaseDuplicates with this case_id, we'll recreate them later
        CaseDuplicate.objects.filter(action=self, case_id=case_id).delete()
        return False

    def _update_cases(self, domain, rule, duplicate_case_ids):
        """Updates all the duplicate cases according to the rule
        """
        duplicate_cases = CaseAccessors(domain).get_cases(list(duplicate_case_ids))
        case_updates = self._get_case_updates(duplicate_cases)
        for case_update_batch in chunked(case_updates, 100):
            result = bulk_update_cases(
                domain,
                case_update_batch,
                device_id="CaseDeduplicationActionDefinition-update-cases",
                xmlns=DEDUPE_XMLNS,
            )
            rule.log_submission(result[0].form_id)
        return len(case_updates)

    def _get_case_updates(self, duplicate_cases):
        cases_to_update = defaultdict(dict)
        for duplicate_case in duplicate_cases:
            cases_to_update.update(self.get_case_and_ancestor_updates(duplicate_case))
        return [
            (case_id, case_properties, False) for case_id, case_properties in cases_to_update.items()
        ]


class CaseDuplicate(models.Model):
    id = models.BigAutoField(primary_key=True)
    case_id = models.CharField(max_length=126, null=True, db_index=True)
    action = models.ForeignKey("CaseDeduplicationActionDefinition", on_delete=models.CASCADE)
    potential_duplicates = models.ManyToManyField('self', symmetrical=True)

    class Meta:
        unique_together = ('case_id', 'action')

    def __str__(self):
        return f"CaseDuplicate(id={self.id}, case_id={self.case_id}, action_id={self.action_id})"

    @classmethod
    def remove_unique_cases(cls, action, case_id):
        # Given a case_id that is no longer a duplicate, ensure there are no
        # other CaseDuplicates that were only pointing to this case
        return (
            cls.objects
            .filter(action=action)
            .filter(Q(potential_duplicates__case_id=case_id))
            .annotate(potential_duplicates_count=models.Count("potential_duplicates"))
            .filter(potential_duplicates_count=1)
            .delete()
        )

    @classmethod
    def bulk_create_duplicate_relationships(cls, action, initial_case, duplicate_case_ids):
        existing_case_duplicates = CaseDuplicate.objects.filter(case_id__in=duplicate_case_ids, action=action)
        existing_case_duplicate_case_ids = [case.case_id for case in existing_case_duplicates]
        case_duplicates = cls.objects.bulk_create([
            cls(case_id=duplicate_case_id, action=action)
            for duplicate_case_id in duplicate_case_ids
            if duplicate_case_id not in existing_case_duplicate_case_ids
        ])
        case_duplicates += existing_case_duplicates
        initial_case_duplicate = next(
            duplicate for duplicate in case_duplicates if duplicate.case_id == initial_case.case_id
        )
        # Create symmetrical many-to-many relationship between each duplicate in bulk
        through_models = [
            through_model
            for case_duplicate in case_duplicates
            if case_duplicate.case_id != initial_case.case_id

            for through_model in (
                cls.potential_duplicates.through(
                    from_caseduplicate=initial_case_duplicate,
                    to_caseduplicate=case_duplicate,
                ),
                cls.potential_duplicates.through(
                    from_caseduplicate=case_duplicate,
                    to_caseduplicate=initial_case_duplicate,
                )
            )
        ]
        cls.potential_duplicates.through.objects.bulk_create(through_models)


class VisitSchedulerIntegrationHelper(object):

    class VisitSchedulerIntegrationException(Exception):
        pass

    def __init__(self, case, scheduler_module_info):
        self.case = case
        self.scheduler_module_info = scheduler_module_info

    @classmethod
    @quickcache(['domain', 'app_id', 'form_unique_id'], timeout=60 * 60, memoize_timeout=60, session_function=None)
    def get_visit_scheduler_module_and_form(cls, domain, app_id, form_unique_id):
        app = get_latest_released_app(domain, app_id)
        if app is None:
            raise cls.VisitSchedulerIntegrationException("App not found")

        try:
            form = app.get_form(form_unique_id)
        except FormNotFoundException:
            raise cls.VisitSchedulerIntegrationException("Form not found")

        if not isinstance(form, AdvancedForm):
            raise cls.VisitSchedulerIntegrationException("Expected AdvancedForm")

        if not form.schedule:
            raise cls.VisitSchedulerIntegrationException("Expected form.schedule")

        if not form.schedule.enabled:
            raise cls.VisitSchedulerIntegrationException("Expected form.schedule.enabled")

        return form.get_module(), form

    def get_visit_scheduler_form_phase(self, module):
        for i, phase in enumerate(module.schedule_phases):
            for form_reference in phase.forms:
                if form_reference.form_id == self.scheduler_module_info.form_unique_id:
                    # The indexes are 0-based, but the visit scheduler refers to them as being 1-based
                    return i + 1, phase

        raise self.VisitSchedulerIntegrationException("Schedule phase not found")

    def calculate_window_date(self, visit, visit_due_date):
        if self.scheduler_module_info.window_position == VISIT_WINDOW_START:
            return visit_due_date + timedelta(days=visit.starts)
        elif self.scheduler_module_info.window_position == VISIT_WINDOW_END:
            if not isinstance(visit.expires, int):
                raise self.VisitSchedulerIntegrationException("Cannot schedule end date of visit that does not expire")

            return visit_due_date + timedelta(days=visit.expires)
        elif self.scheduler_module_info.window_position == VISIT_WINDOW_DUE_DATE:
            return visit_due_date
        else:
            raise self.VisitSchedulerIntegrationException("Unrecognized value for window_position")

    def get_case_current_schedule_phase(self):
        phase_num = self.case.get_case_property('current_schedule_phase')
        try:
            return int(phase_num)
        except:
            return None

    def get_visit(self, form):
        try:
            visit = form.schedule.visits[self.scheduler_module_info.visit_number]
        except IndexError:
            raise self.VisitSchedulerIntegrationException("Visit not found")

        if visit.repeats:
            raise self.VisitSchedulerIntegrationException("Repeat visits are not supported")

        return visit

    def get_anchor_date(self, anchor_case_property):
        anchor_date = self.case.get_case_property(anchor_case_property)
        anchor_date = _try_date_conversion(anchor_date)
        if isinstance(anchor_date, datetime):
            anchor_date = anchor_date.date()

        if not isinstance(anchor_date, date):
            raise self.VisitSchedulerIntegrationException("Unable to get anchor date")

        return anchor_date

    def get_result(self):
        module, form = self.get_visit_scheduler_module_and_form(
            self.case.domain,
            self.scheduler_module_info.app_id,
            self.scheduler_module_info.form_unique_id
        )

        form_phase_num, phase = self.get_visit_scheduler_form_phase(module)
        if form_phase_num != self.get_case_current_schedule_phase():
            return False, None

        anchor_date = self.get_anchor_date(phase.anchor)
        visit = self.get_visit(form)
        visit_due_date = anchor_date + timedelta(days=visit.due)
        return True, self.calculate_window_date(visit, visit_due_date)


class CreateScheduleInstanceActionDefinition(CaseRuleActionDefinition):
    alert_schedule = models.ForeignKey('scheduling.AlertSchedule', null=True, on_delete=models.PROTECT)
    timed_schedule = models.ForeignKey('scheduling.TimedSchedule', null=True, on_delete=models.PROTECT)

    # A List of [recipient_type, recipient_id]
    recipients = jsonfield.JSONField(default=list)

    # (Optional, ignored if None) The name of a case property whose value will be tracked
    # over time on the schedule instance as last_reset_case_property_value.
    # Every time the case property's value changes, the schedule's start date is
    # reset to the current date.
    # Applicable to AlertSchedules and TimedSchedules
    reset_case_property_name = models.CharField(max_length=126, null=True)

    # (Optional) The name of a case property which represents the date on which to start
    # the schedule instance.
    # Only applicable when the schedule is a TimedSchedule
    start_date_case_property = models.CharField(max_length=126, null=True)

    # (Optional) A specific date which represents the date on which to start
    # the schedule instance.
    # Only applicable when the schedule is a TimedSchedule
    specific_start_date = models.DateField(null=True)

    # (Optional) A dict with the structure represented by SchedulerModuleInfo.
    # enabled must be set to True in this dict in order for it to count.
    # the framework uses info related to the specified visit number to set
    # the start date for any schedule instances created from this CreateScheduleInstanceActionDefinition.
    # Only applicable when the schedule is a TimedSchedule
    scheduler_module_info = jsonfield.JSONField(default=dict)

    class SchedulerModuleInfo(JsonObject):
        # Set to True to enable setting the start date of any schedule instances
        # based on the visit scheduler info details below
        enabled = BooleanProperty(default=False)

        # The app that contains the visit scheduler form being referenced
        app_id = StringProperty()

        # The unique_id of the visit scheduler form in the above app
        form_unique_id = StringProperty()

        # The visit number from which to pull the start date for any schedule
        # instances; this should be the 0-based index in the FormSchedule.visits list
        visit_number = IntegerProperty()

        # VISIT_WINDOW_START - the start date used will be the first date in the window
        # VISIT_WINDOW_END - the start date used will be the last date in the window
        # VISIT_WINDOW_DUE_DATE - the start date used will be the due date of the visit
        window_position = StringProperty(choices=[VISIT_WINDOW_START, VISIT_WINDOW_END, VISIT_WINDOW_DUE_DATE])

    @property
    def schedule(self):
        if self.alert_schedule_id:
            return self.alert_schedule
        elif self.timed_schedule_id:
            return self.timed_schedule

        raise ValueError("Expected a schedule")

    @schedule.setter
    def schedule(self, value):
        from corehq.messaging.scheduling.models import (
            AlertSchedule,
            TimedSchedule,
        )

        self.alert_schedule = None
        self.timed_schedule = None

        if isinstance(value, AlertSchedule):
            self.alert_schedule = value
        elif isinstance(value, TimedSchedule):
            self.timed_schedule = value
        else:
            raise TypeError("Expected an instance of AlertSchedule or TimedSchedule")

    def notify_scheduler_integration_exception(self, case, scheduler_module_info):
        details = scheduler_module_info.to_json()
        details.update({
            'domain': case.domain,
            'case_id': case.case_id,
        })
        notify_exception(
            None,
            message="Error in messaging / visit scheduler integration",
            details=details
        )

    def get_date_from_start_date_case_property(self, case):
        value = case.get_case_property(self.start_date_case_property)
        if not value:
            return None

        value = _try_date_conversion(value)
        if isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value

        return None

    def when_case_matches(self, case, rule):
        schedule = self.schedule
        if isinstance(schedule, AlertSchedule):
            refresh_case_alert_schedule_instances(case, schedule, self, rule)
        elif isinstance(schedule, TimedSchedule):
            kwargs = {}
            scheduler_module_info = self.get_scheduler_module_info()

            # Figure out what to use as the start date of the schedule instance.
            # Use the information from start_date_case_property, specific_start_date, or
            # scheduler_module_info. If no start date configuration is provided in
            # any of those options, then the date the rule is satisfied will be used
            # as the start date for the schedule instance.

            if self.start_date_case_property:
                start_date = self.get_date_from_start_date_case_property(case)
                if not start_date:
                    # The case property doesn't reference a date, so delete any
                    # schedule instances pertaining to this rule and case and return
                    self.delete_schedule_instances(case)
                    return CaseRuleActionResult()

                kwargs['start_date'] = start_date
            elif self.specific_start_date:
                kwargs['start_date'] = self.specific_start_date
            elif scheduler_module_info.enabled:
                try:
                    case_phase_matches, schedule_instance_start_date = VisitSchedulerIntegrationHelper(case,
                        scheduler_module_info).get_result()
                except VisitSchedulerIntegrationHelper.VisitSchedulerIntegrationException:
                    self.delete_schedule_instances(case)
                    self.notify_scheduler_integration_exception(case, scheduler_module_info)
                    return CaseRuleActionResult()

                if not case_phase_matches:
                    # The case is not in the matching schedule phase, so delete
                    # schedule instances pertaining to this rule and case and return
                    self.delete_schedule_instances(case)
                    return CaseRuleActionResult()
                else:
                    kwargs['start_date'] = schedule_instance_start_date

            refresh_case_timed_schedule_instances(case, schedule, self, rule, **kwargs)

        return CaseRuleActionResult()

    def when_case_does_not_match(self, case, rule):
        self.delete_schedule_instances(case)
        return CaseRuleActionResult()

    def delete_schedule_instances(self, case):
        if self.alert_schedule_id:
            get_case_alert_schedule_instances_for_schedule_id(case.case_id, self.alert_schedule_id).delete()

        if self.timed_schedule_id:
            get_case_timed_schedule_instances_for_schedule_id(case.case_id, self.timed_schedule_id).delete()

    def get_scheduler_module_info(self):
        return self.SchedulerModuleInfo(**self.scheduler_module_info)

    def set_scheduler_module_info(self, info):
        if not isinstance(info, self.SchedulerModuleInfo):
            raise ValueError("Expected CreateScheduleInstanceActionDefinition.SchedulerModuleInfo")

        self.scheduler_module_info = info.to_json()


class CaseRuleSubmission(models.Model):
    """This model records which forms were submitted as a result of a case
    update rule. This serves both as a log as well as providing the ability
    to undo the effects of rules in case of errors.

    This data is not stored permanently but is removed after 90 days (see tasks file)
    """
    domain = models.CharField(max_length=126)
    rule = models.ForeignKey('AutomaticUpdateRule', on_delete=models.PROTECT)

    # The timestamp that this record was created on
    created_on = models.DateTimeField(db_index=True)

    # Reference to XFormInstance.form_id or XFormInstanceSQL.form_id
    form_id = models.CharField(max_length=255, unique=True, db_index=True)

    # A shortcut to keep track of which forms get archived
    archived = models.BooleanField(default=False)

    class Meta(object):
        index_together = (
            ('domain', 'created_on'),
            ('domain', 'rule', 'created_on'),
        )


class CaseRuleUndoer(object):

    def __init__(self, domain, rule_id=None, since=None):
        self.domain = domain
        self.rule_id = rule_id
        self.since = since

    def get_submission_queryset(self):
        qs = CaseRuleSubmission.objects.filter(
            domain=self.domain,
            archived=False,
        )

        if self.rule_id is not None:
            qs = qs.filter(rule_id=self.rule_id)

        if self.since:
            qs = qs.filter(created_on__gte=self.since)

        return qs

    def bulk_undo(self, progress_bar=False):
        chunk_size = 100
        result = {
            'processed': 0,
            'skipped': 0,
            'archived': 0,
        }

        form_ids = list(self.get_submission_queryset().values_list('form_id', flat=True))
        form_id_chunks = chunked(form_ids, chunk_size)
        if progress_bar:
            length = len(form_ids) // chunk_size
            if len(form_ids) % chunk_size > 0:
                length += 1
            form_id_chunks = with_progress_bar(form_id_chunks, length=length)

        for form_id_chunk in form_id_chunks:
            archived_form_ids = []
            for form in FormAccessors(self.domain).iter_forms(form_id_chunk):
                result['processed'] += 1

                if not form.is_normal or any([u.creates_case() for u in get_case_updates(form)]):
                    result['skipped'] += 1
                    continue

                if not form.is_archived:
                    form.archive(user_id=SYSTEM_USER_ID)
                result['archived'] += 1
                archived_form_ids.append(form.form_id)

            CaseRuleSubmission.objects.filter(form_id__in=archived_form_ids).update(archived=True)

        return result


class DomainCaseRuleRun(models.Model):
    STATUS_RUNNING = 'R'
    STATUS_FINISHED = 'F'
    STATUS_HALTED = 'H'

    domain = models.CharField(max_length=126)
    case_type = models.CharField(max_length=255, null=True)
    started_on = models.DateTimeField(db_index=True)
    finished_on = models.DateTimeField(null=True)
    status = models.CharField(max_length=1)

    cases_checked = models.IntegerField(default=0)
    num_updates = models.IntegerField(default=0)
    num_closes = models.IntegerField(default=0)
    num_related_updates = models.IntegerField(default=0)
    num_related_closes = models.IntegerField(default=0)
    num_creates = models.IntegerField(default=0)

    dbs_completed = JSONField(default=list)

    class Meta(object):
        index_together = (
            ('domain', 'started_on'),
        )

    @classmethod
    def done(cls, run_id, status, cases_checked, result, db=None):
        if not isinstance(result, CaseRuleActionResult):
            raise TypeError("Expected an instance of CaseRuleActionResult")

        if status not in (cls.STATUS_HALTED, cls.STATUS_FINISHED):
            raise ValueError("Expected STATUS_HALTED or STATUS_FINISHED")

        with CriticalSection(['update-domain-case-rule-run-%s' % run_id]):
            run = cls.objects.get(pk=run_id)

            run.cases_checked += cases_checked
            run.num_updates += result.num_updates
            run.num_closes += result.num_closes
            run.num_related_updates += result.num_related_updates
            run.num_related_closes += result.num_related_closes
            run.num_creates += result.num_creates

            if db:
                run.dbs_completed.append(db)
                all_dbs = get_db_aliases_for_partitioned_query()

                if set(all_dbs) == set(run.dbs_completed):
                    run.finished_on = datetime.utcnow()
            else:
                run.finished_on = datetime.utcnow()

            if status == cls.STATUS_HALTED:
                run.status = status
            elif status == cls.STATUS_FINISHED and run.status != cls.STATUS_HALTED and run.finished_on:
                run.status = status

            run.save()
            return run
