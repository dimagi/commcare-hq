from __future__ import absolute_import
import hashlib

from jsonobject import DefaultProperty, BooleanProperty
from jsonobject.properties import ListProperty, StringProperty
import six

from corehq.apps.userreports.decorators import ucr_context_cache
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from custom.enikshay.case_utils import get_open_referral_case_from_person, get_latest_trail_case_from_person, \
    get_open_episode_case_from_person, get_most_recent_episode_case_from_person, \
    get_most_recent_referral_case_from_person
from custom.enikshay.exceptions import ENikshayCaseNotFound
from dimagi.ext.jsonobject import JsonObject
from dimagi.utils.dates import force_to_datetime


@ucr_context_cache(vary_on=('case_id',))
def _get_case_forms(domain, case_id, context):
    return FormProcessorInterface(domain).get_case_forms(case_id)


class FirstCaseFormWithXmlns(JsonObject):
    type = TypeProperty('first_case_form_with_xmlns')
    xmlns = DefaultProperty(required=True)
    case_id_expression = DefaultProperty(required=True)
    reverse = BooleanProperty(default=False)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        assert isinstance(self.xmlns, (six.string_types, list))

        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        assert context.root_doc['domain']
        return self._get_forms(case_id, context)

    def _get_forms(self, case_id, context):
        domain = context.root_doc['domain']

        xmlns = [self.xmlns] if isinstance(self.xmlns, six.string_types) else self.xmlns
        xforms = _get_case_forms(domain, case_id, context)
        xforms = sorted(
            [form for form in xforms if form.xmlns in xmlns and form.domain == domain],
            key=lambda x: x.received_on
        )
        if not xforms:
            form = None
        else:
            index = -1 if self.reverse else 0
            form = xforms[index].to_json()
        return form


def first_case_form_with_xmlns_expression(spec, context):
    wrapped = FirstCaseFormWithXmlns.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped


class CountCaseFormsWithXmlns(JsonObject):
    type = TypeProperty('count_case_forms_with_xmlns')
    xmlns = DefaultProperty(required=True)
    case_id_expression = DefaultProperty(required=True)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        assert isinstance(self.xmlns, (six.string_types, list))

        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        assert context.root_doc['domain']
        return self._count_forms(case_id, context)

    def _count_forms(self, case_id, context):
        domain = context.root_doc['domain']

        xmlns = [self.xmlns] if isinstance(self.xmlns, six.string_types) else self.xmlns
        xforms = _get_case_forms(domain, case_id, context)
        count = len([form for form in xforms if form.xmlns in xmlns and form.domain == domain])
        return count


def count_case_forms_with_xmlns_expression(spec, context):
    wrapped = CountCaseFormsWithXmlns.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped


class ConcatenateStrings(JsonObject):
    type = TypeProperty('concatenate_strings')
    expressions = ListProperty(required=True)
    separator = StringProperty(required=True)

    def configure(self, expressions):
        self._expression_fns = expressions

    def __call__(self, item, context=None):
        return self.separator.join(
            [
                six.text_type(expression(item, context)) for expression in self._expression_fns
                if expression(item, context)
            ]
        )


def concatenate_strings_expression(spec, context):
    wrapped = ConcatenateStrings.wrap(spec)
    wrapped.configure(
        [ExpressionFactory.from_spec(e, context) for e in wrapped.expressions],
    )
    return wrapped


class ReferralExpressionBase(JsonObject):
    person_id_expression = DefaultProperty(required=True)

    def configure(self, person_id_expression):
        self._person_id_expression = person_id_expression

    def __call__(self, item, context=None):
        person_id = self._person_id_expression(item, context)
        domain = context.root_doc['domain']
        if not person_id:
            return None

        referral = self._get_referral(context, domain, person_id)
        if referral:
            return self._handle_referral_case(referral)
        trail = self._get_trail(context, domain, person_id)
        if trail:
            return self._handle_trail_case(context, trail, domain)
        return None

    @staticmethod
    @ucr_context_cache(vary_on=('person_id',))
    def _get_referral(context, domain, person_id):
        referral = get_open_referral_case_from_person(domain, person_id)
        if referral and (referral.dynamic_case_properties().get("referral_status") == "rejected"):
            referral = None
        return referral

    @staticmethod
    @ucr_context_cache(vary_on=('referral_id',))
    def _get_referral_by_id(context, domain, referral_id):
        return CaseAccessors(domain).get_case(referral_id)

    @staticmethod
    @ucr_context_cache(vary_on=('person_id',))
    def _get_trail(context, domain, person_id):
        return get_latest_trail_case_from_person(domain, person_id)

    def _handle_referral_case(self, referral):
        raise NotImplementedError

    def _handle_trail_case(self, context, trail, domain):
        raise NotImplementedError


class ReferredBy(ReferralExpressionBase):
    type = TypeProperty("enikshay_referred_by")

    def _handle_referral_case(self, referral):
        return referral.opened_by

    def _handle_trail_case(self, context, trail, domain):
        return trail.owner_id


def referred_by_expression(spec, context):
    wrapped = ReferredBy.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class ReferredTo(ReferralExpressionBase):
    """
    An expression that returns the id of a location that the person was referred to.
    """
    type = TypeProperty('enikshay_referred_to')

    def _handle_referral_case(self, referral):
        return referral.owner_id

    def _handle_trail_case(self, context, trail, domain):
        # We can't use trail.accepted_by because that is a human readable name, not an id
        referral_id = trail.dynamic_case_properties().get("referral_id")
        if referral_id:
            referral = self._get_referral_by_id(context, domain, referral_id)
            return self._handle_referral_case(referral)
        return None


def referred_to_expression(spec, context):
    wrapped = ReferredTo.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class DateOfReferral(ReferralExpressionBase):
    type = TypeProperty('enikshay_date_of_referral')

    def _handle_referral_case(self, referral):
        return referral.dynamic_case_properties().get("referral_initiated_date")

    def _handle_trail_case(self, context, trail, domain):
        referral_id = trail.dynamic_case_properties().get("referral_id")
        if referral_id:
            referral = self._get_referral_by_id(context, domain, referral_id)
            return self._handle_referral_case(referral)
        return None


def date_of_referral_expression(spec, context):
    wrapped = DateOfReferral.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class DateOfAcceptance(ReferralExpressionBase):
    type = TypeProperty("enikshay_date_of_acceptance")

    def __call__(self, item, context=None):
        person_id = self._person_id_expression(item, context)
        domain = context.root_doc['domain']
        if not person_id:
            return None
        trail = get_latest_trail_case_from_person(domain, person_id)
        if trail:
            return trail.opened_on
        return None


def date_of_acceptance_expression(spec, context):
    wrapped = DateOfAcceptance.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class MonthExpression(JsonObject):
    type = TypeProperty('month_expression')
    month_expression = DefaultProperty(required=True)

    def configure(self, month_expression):
        self._month_expression = month_expression

    def __call__(self, item, context=None):
        try:
            date = force_to_datetime(self._month_expression(item, context))
        except ValueError:
            return ''
        if not date:
            return ''
        return str(date.month)


def month_expression(spec, context):
    wrapped = MonthExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.month_expression, context)
    )
    return wrapped


class EpisodeFromPersonExpression(JsonObject):
    type = TypeProperty('enikshay_episode_from_person')
    person_id_expression = DefaultProperty(required=True)

    def configure(self, person_id_expression):
        self._person_id_expression = person_id_expression

    def __call__(self, item, context=None):
        person_id = self._person_id_expression(item, context)
        domain = context.root_doc['domain']
        if not person_id:
            return None
        try:
            episode = get_open_episode_case_from_person(domain, person_id)
        except ENikshayCaseNotFound:
            return None
        if episode:
            return episode.to_json()
        return None


def episode_from_person_expression(spec, context):
    wrapped = EpisodeFromPersonExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class KeyPopulationsExpression(JsonObject):
    type = TypeProperty('enikshay_key_populations')
    key_populations_expression = DefaultProperty(required=True)

    def configure(self, key_populations_expression):
        self._key_populations_expression = key_populations_expression

    def __call__(self, item, context=None):
        key_populations_value = self._key_populations_expression(item, context)
        if not key_populations_value:
            return ''
        return ', '.join(key_populations_value.split(' '))


def key_populations_expression(spec, context):
    wrapped = KeyPopulationsExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.key_populations_expression, context)
    )
    return wrapped


class MostRecentReferralCaseFromPerson(JsonObject):
    """
    An expression that returns the the most recent Referral Case from Person which pass the filters:
       -> referral_status != 'rejected' and 'referral_closed_reason' != 'duplicate_referral_reconciliation'
    """
    type = TypeProperty('enikshay_most_recent_referral_from_person')
    person_id_expression = DefaultProperty(required=True)

    def configure(self, person_id_expression):
        self._person_id_expression = person_id_expression

    def __call__(self, item, context=None):
        person_id = self._person_id_expression(item, context)
        domain = context.root_doc['domain']

        @ucr_context_cache(vary_on=('person_id',))
        def _cached_get(person_id, context):
            if not person_id:
                return None
            try:
                referral = get_most_recent_referral_case_from_person(domain, person_id)
            except ENikshayCaseNotFound:
                referral = None
            if referral:
                return referral.to_json()

        return _cached_get(person_id, context)


def most_recent_referral_expression(spec, context):
    wrapped = MostRecentReferralCaseFromPerson.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


class MostRecentEpisodeCaseFromPerson(JsonObject):
    """
    An expression that returns the the most recent Referral Case from Person which pass the filters:
       -> referral_status != 'rejected' and 'referral_closed_reason' != 'duplicate_referral_reconciliation'
    """
    type = TypeProperty('enikshay_most_recent_episode_from_person')
    person_id_expression = DefaultProperty(required=True)

    def configure(self, person_id_expression):
        self._person_id_expression = person_id_expression

    def __call__(self, item, context=None):
        person_id = self._person_id_expression(item, context)

        @ucr_context_cache(vary_on=('person_id',))
        def _cached_get(person_id, context):
            if not person_id:
                return None
            try:
                episode = get_most_recent_episode_case_from_person(domain, person_id)
            except ENikshayCaseNotFound:
                episode = None
            if episode:
                return episode.to_json()

        return _cached_get(person_id, context)


def most_recent_episode_expression(spec, context):
    wrapped = MostRecentEpisodeCaseFromPerson.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped
