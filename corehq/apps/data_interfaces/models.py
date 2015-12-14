import re
from casexml.apps.case.models import CommCareCase
from corehq.apps.es.cases import CaseES
from datetime import date, datetime, time, timedelta
from dateutil.parser import parse
from django.db import models
from corehq.apps.hqcase.utils import update_case


ALLOWED_DATE_REGEX = re.compile('^\d{4}-\d{2}-\d{2}')
AUTO_UPDATE_XMLNS = 'http://commcarehq.org/hq_case_update_rule'


class AutomaticUpdateRule(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=126)
    case_type = models.CharField(max_length=126)
    active = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    last_run = models.DateTimeField(null=True)

    # For performance reasons, the server_modified_boundary is a
    # required part of the criteria and should be set to the minimum
    # number of days old that a case's server_modified_on date must be
    # before we run the rule against it.
    server_modified_boundary = models.IntegerField()

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
        min_boundary = min([rule.server_modified_boundary for rule in rules])
        date = now - timedelta(days=min_boundary)
        return date

    @classmethod
    def get_case_ids(cls, domain, boundary_date, case_type):
        query = (CaseES()
                 .domain(domain)
                 .case_type(case_type)
                 .server_modified_range(lte=boundary_date)
                 .is_closed(closed=False)
                 .fields([]))
        results = query.run()
        return results.doc_ids

    def rule_matches_case(self, case, now):
        if case.type != self.case_type:
            return False

        if (case.server_modified_on >
                (now - timedelta(days=self.server_modified_boundary))):
            return False

        return all([criterion.matches(case, now)
                   for criterion in self.automaticupdaterulecriteria_set.all()])

    def apply_actions(self, case):
        properties = {}
        close = False

        for action in self.automaticupdateaction_set.all():
            if action.action == AutomaticUpdateAction.ACTION_UPDATE:
                properties[action.property_name] = action.property_value
            elif action.action == AutomaticUpdateAction.ACTION_CLOSE:
                close = True

        update_case(case.domain, case.get_id, case_properties=properties, close=close,
            xmlns=AUTO_UPDATE_XMLNS)
        return close

    def apply_rule(self, case, now):
        """
        Returns True if the case was closed, False otherwise.
        """
        if self.deleted:
            raise Exception("Attempted to call apply_rule on a deleted rule")

        if not self.active:
            raise Exception("Attempted to call apply_rule on an inactive rule")

        if not isinstance(case, CommCareCase) or case.domain != self.domain:
            raise Exception("Invalid case given")

        if case.doc_type != 'CommCareCase':
            # Exclude deleted cases
            return False

        if case.closed:
            return False

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

    def check_days_since(self, case, now):
        date_to_check = case.get_case_property(self.property_name)
        if (
            not isinstance(date_to_check, date) and
            isinstance(date_to_check, basestring) and
            ALLOWED_DATE_REGEX.match(date_to_check)
        ):
            date_to_check = parse(date_to_check)

        if not isinstance(date_to_check, date):
            return False

        if not isinstance(date_to_check, datetime):
            date_to_check = datetime.combine(date_to_check, time(0, 0))

        days = int(self.property_value)
        return date_to_check <= (now - timedelta(days=days))

    def check_equal(self, case, now):
        return case.get_case_property(self.property_name) == self.property_value

    def check_not_equal(self, case, now):
        return case.get_case_property(self.property_name) != self.property_value

    def check_has_value(self, case, now):
        value = case.get_case_property(self.property_name)
        if value is None:
            return False
        if isinstance(value, basestring) and not value.strip():
            return False
        return True

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
