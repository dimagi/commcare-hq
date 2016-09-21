import re
from collections import defaultdict

from casexml.apps.case.models import CommCareCase
from corehq.apps.es.cases import CaseES
from corehq.form_processor.exceptions import CaseNotFound
from couchdbkit.exceptions import ResourceNotFound
from datetime import date, datetime, time, timedelta
from dateutil.parser import parse
from django.db import models
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.models import CommCareCaseSQL

ALLOWED_DATE_REGEX = re.compile('^\d{4}-\d{2}-\d{2}')
AUTO_UPDATE_XMLNS = 'http://commcarehq.org/hq_case_update_rule'


class PropertyTypeChoices(object):
    EXACT = "Exact"
    CASE_PROPERTY = "Case Property"

    choices = (
        (EXACT, EXACT),
        (CASE_PROPERTY, CASE_PROPERTY)
    )


class AutomaticUpdateRule(models.Model):
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

    class Meta:
        app_label = "data_interfaces"

    @classmethod
    def by_domain(cls, domain, active_only=True):
        filters = {'domain': domain}
        if active_only:
            filters['active'] = True
        return AutomaticUpdateRule.objects.filter(deleted=False, **filters)

    @classmethod
    def organize_rules_by_case_type(cls, rules):
        rules_by_case_type = {}
        for rule in rules:
            if rule.case_type not in rules_by_case_type:
                rules_by_case_type[rule.case_type] = [rule]
            else:
                rules_by_case_type[rule.case_type].append(rule)
        return rules_by_case_type

    @classmethod
    def get_boundary_date(cls, rules, now):
        min_boundary = None
        for rule in rules:
            if not rule.server_modified_boundary:
                return None
            elif not min_boundary:
                min_boundary = rule.server_modified_boundary
            elif rule.server_modified_boundary < min_boundary:
                min_boundary = rule.server_modified_boundary
        date = now - timedelta(days=min_boundary)
        return date

    @classmethod
    def get_case_ids(cls, domain, case_type, boundary_date=None):
        query = (CaseES()
                 .domain(domain)
                 .case_type(case_type)
                 .is_closed(closed=False)
                 .exclude_source())
        if boundary_date is not None:
            query = query.server_modified_range(lte=boundary_date)
        results = query.run()
        return results.doc_ids

    def rule_matches_case(self, case, now):
        try:
            return self._rule_matches_case(case, now)
        except (CaseNotFound, ResourceNotFound):
            # This might happen if the rule references a parent case and the
            # parent case is not found
            return False

    def _rule_matches_case(self, case, now):
        if case.type != self.case_type:
            return False

        if self.filter_on_server_modified and \
                (case.server_modified_on > (now - timedelta(days=self.server_modified_boundary))):
            return False

        return all([criterion.matches(case, now)
                   for criterion in self.automaticupdaterulecriteria_set.all()])

    def apply_actions(self, case):
        cases_to_update = defaultdict(dict)
        close = False

        def _get_case_property_value(current_case, name):
            return current_case.resolve_case_property(name)[0].value

        def _add_update_property(name, value, current_case):
            while name.startswith('parent/'):
                name = name[7:]
                current_case = current_case.parent
            cases_to_update[current_case.case_id][name] = value

        for action in self.automaticupdateaction_set.all():
            if action.action == AutomaticUpdateAction.ACTION_UPDATE:
                # break this out as helper function?
                if action.property_value_type == PropertyTypeChoices.CASE_PROPERTY:
                    value = _get_case_property_value(case, action.property_value)
                else:
                    value = action.property_value

                if value != _get_case_property_value(case, action.property_name):
                    _add_update_property(action.property_name, value, case)
            elif action.action == AutomaticUpdateAction.ACTION_CLOSE:
                close = True

        for id, properties in cases_to_update.items():
            close_case = close if id == case.case_id else False
            update_case(case.domain, id, case_properties=properties, close=close_case,
                xmlns=AUTO_UPDATE_XMLNS)

        return close

    def apply_rule(self, case, now):
        """
        :return: True to stop processing further rules on the case (e.g., the
        case is closed or deleted), False otherwise
        """
        if self.deleted:
            raise Exception("Attempted to call apply_rule on a deleted rule")

        if not self.active:
            raise Exception("Attempted to call apply_rule on an inactive rule")

        if not isinstance(case, (CommCareCase, CommCareCaseSQL)) or case.domain != self.domain:
            raise Exception("Invalid case given")

        if case.is_deleted or case.closed:
            return True

        if self.rule_matches_case(case, now):
            return self.apply_actions(case)
        return False

    def activate(self, active=True):
        self.active = active
        self.save()

    def soft_delete(self):
        self.deleted = True
        self.save()


class AutomaticUpdateRuleCriteria(models.Model):
    MATCH_DAYS_SINCE = 'DAYS'
    MATCH_EQUAL = 'EQUAL'
    MATCH_NOT_EQUAL = 'NOT_EQUAL'
    MATCH_HAS_VALUE = 'HAS_VALUE'

    MATCH_TYPE_CHOICES = (
        (MATCH_DAYS_SINCE, MATCH_DAYS_SINCE),
        (MATCH_EQUAL, MATCH_EQUAL),
        (MATCH_NOT_EQUAL, MATCH_NOT_EQUAL),
        (MATCH_HAS_VALUE, MATCH_HAS_VALUE),
    )

    rule = models.ForeignKey('AutomaticUpdateRule', on_delete=models.PROTECT)
    property_name = models.CharField(max_length=126)
    property_value = models.CharField(max_length=126, null=True)
    match_type = models.CharField(max_length=10, choices=MATCH_TYPE_CHOICES)

    class Meta:
        app_label = "data_interfaces"

    def get_case_values(self, case):
        values = case.resolve_case_property(self.property_name)
        return [element.value for element in values]

    def check_days_since(self, case, now):
        values = self.get_case_values(case)
        for date_to_check in values:
            if (
                not isinstance(date_to_check, date) and
                isinstance(date_to_check, basestring) and
                ALLOWED_DATE_REGEX.match(date_to_check)
            ):
                date_to_check = parse(date_to_check)

            if not isinstance(date_to_check, date):
                continue

            if not isinstance(date_to_check, datetime):
                date_to_check = datetime.combine(date_to_check, time(0, 0))

            days = int(self.property_value)
            if date_to_check <= (now - timedelta(days=days)):
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
            if isinstance(value, basestring) and not value.strip():
                continue
            return True

        return False

    def matches(self, case, now):
        return {
            self.MATCH_DAYS_SINCE: self.check_days_since,
            self.MATCH_EQUAL: self.check_equal,
            self.MATCH_NOT_EQUAL: self.check_not_equal,
            self.MATCH_HAS_VALUE: self.check_has_value,
        }.get(self.match_type)(case, now)


class AutomaticUpdateAction(models.Model):
    ACTION_UPDATE = 'UPDATE'
    ACTION_CLOSE = 'CLOSE'

    ACTION_CHOICES = (
        (ACTION_UPDATE, ACTION_UPDATE),
        (ACTION_CLOSE, ACTION_CLOSE),
    )


    rule = models.ForeignKey('AutomaticUpdateRule', on_delete=models.PROTECT)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    # property_name and property_value are ignored unless action is UPDATE
    property_name = models.CharField(max_length=126, null=True)
    property_value = models.CharField(max_length=126, null=True)

    property_value_type = models.CharField(max_length=15,
                                           choices=PropertyTypeChoices.choices,
                                           default=PropertyTypeChoices.EXACT)

    class Meta:
        app_label = "data_interfaces"
