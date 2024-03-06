import re

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.app_manager.const import (
    SCHEDULE_DATE_CASE_OPENED,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
    SCHEDULE_LAST_VISIT,
    SCHEDULE_LAST_VISIT_DATE,
    SCHEDULE_MAX_DATE,
    SCHEDULE_PHASE,
    SCHEDULE_TERMINATED,
    USERCASE_TYPE,
)
from corehq.apps.app_manager.exceptions import (
    CaseXPathValidationError,
    LocationXPathValidationError,
    ScheduleError,
)

# Note that this may match strings that do not need interpolation, such as "blah == 'ellipsis...'",
# but it should not miss any strings that do need interpolation.
DOT_INTERPOLATE_PATTERN = r'(\D|^)\.(\D|$)'

CASE_REFERENCE_VALIDATION_ERROR = gettext_lazy(
    "Your form uses an expression which references a case, but cases are not available. Please go to form "
    "settings and either remove the case reference or (1) make sure that the menu mode is set to display the "
    "menu first and then form, and (2) make sure that all forms in this case list update or close a case "
    "(which means registration forms must go in a different case list)."
)


def dot_interpolate(string, replacement):
    """
    Replaces non-decimal, non-quoted dots in `string` with `replacement`
    """
    quote = ""  # " or ' if inside a string, else blank
    new = ""
    i = 0
    while i < len(string):
        # Ignore backslash-escaped characters
        if string[i] == "\\":
            new += string[i:i + 2]
            i = i + 2
            continue

        if quote:
            # We're inside a quoted string: just check to see if it's ending
            if string[i] == quote:
                quote = ""
            new += string[i]
        else:
            if string[i] in "\"'":
                # We're entering a quoted string: just record the quote type
                quote = string[i]
                new += string[i]
            else:
                # Non-quote character, not inside a quoted string
                if string[i] == ".":
                    # Replace dot with replacement, unless this looks like a decimal number
                    if (i == 0 or re.match(r'\D', string[i - 1])):
                        if (i == len(string) - 1 or re.match(r'\D', string[i + 1])):
                            new += replacement
                            i = i + 1
                            continue
                new += string[i]
        i = i + 1
    return new


def _ensure_no_case_references(string, module, form, interpolate_dots=True):
    bad_references = [
        '#case' in string,
        '#parent' in string,
        '#host' in string,
    ]
    if interpolate_dots:
        bad_references.append(re.search(DOT_INTERPOLATE_PATTERN, string) and dot_interpolate(string, "") != string)
    if any(bad_references):
        # At the moment this function is only used by module and form filters.
        # If that changes, amend the error message accordingly.
        raise CaseXPathValidationError(_(CASE_REFERENCE_VALIDATION_ERROR), module=module, form=form)


def interpolate_xpath(string, case_xpath=None, fixture_xpath=None, module=None, form=None, interpolate_dots=True):
    """
    Replace xpath shortcuts with full value.
    """
    if case_xpath is None:
        _ensure_no_case_references(string, module, form, interpolate_dots)

    replacements = {
        '#user': UsercaseXPath().case(),
        '#session/': session_var('', path=''),
    }
    if fixture_xpath:
        replacements['$fixture_value'] = fixture_xpath

    if case_xpath:
        replacements['#case'] = case_xpath
        replacements['#parent'] = CaseIDXPath(case_xpath + '/index/parent').case()
        replacements['#host'] = CaseIDXPath(case_xpath + '/index/host').case()

    for pattern, repl in replacements.items():
        string = string.replace(pattern, repl)

    if case_xpath:
        return dot_interpolate(string, case_xpath)

    return string


def session_var(var, path='data'):
    session = XPath("instance('commcaresession')/session")
    if path:
        session = session.slash(path)

    return session.slash(var)


class XPath(str):

    def __new__(cls, string='', compound=False):
        return super(XPath, cls).__new__(cls, string)

    def __init__(self, string='', compound=False):
        self.compound = compound

    def paren(self, force=False):
        return str(self) if not (force or self.compound) else '({})'.format(self)

    def slash(self, xpath):
        if self:
            return XPath('%s/%s' % (self, xpath))
        else:
            return XPath(xpath)

    def select_raw(self, expression):
        return XPath("{self}[{expression}]".format(self=self, expression=expression))

    def select(self, ref, value, quote=None):
        if quote is None:
            quote = not isinstance(value, XPath)
        if quote:
            value = XPath.string(value)
        return XPath("{self}[{ref}={value}]".format(self=self, ref=ref, value=value))

    def count(self):
        return XPath('count({self})'.format(self=self))

    def eq(self, b):
        return XPath('{} = {}'.format(self, b))

    def neq(self, b):
        return XPath('{} != {}'.format(self, b))

    def gt(self, b):
        return XPath('{} > {}'.format(self, b))

    @staticmethod
    def expr(template, args, chainable=False):
        if chainable:
            template = template.join(['{}'] * len(args))

        def check_type(arg):
            return arg if isinstance(arg, XPath) else XPath(arg)

        args = [check_type(arg) for arg in args]

        return XPath(template.format(*[x.paren() for x in args]), compound=True)

    @staticmethod
    def if_(a, b, c):
        return XPath("if({}, {}, {})".format(a, b, c))

    @staticmethod
    def string(a):
        # todo: escape text
        return XPath("'{}'".format(a))

    @staticmethod
    def and_(*args):
        return XPath.expr(' and ', args, chainable=True)

    @staticmethod
    def or_(*args):
        return XPath.expr(' or ', args, chainable=True)

    @staticmethod
    def not_(a):
        return XPath.expr("not({})", [a])

    @staticmethod
    def date(a):
        return XPath('date({})'.format(a))

    @staticmethod
    def int(a):
        return XPath('int({})'.format(a))

    @staticmethod
    def empty_string():
        return XPath("''")


class CaseSelectionXPath(XPath):
    selector = ''

    def case(self, instance_name='casedb', case_name='case'):
        return CaseXPath("instance('{inst}')/{root}/{case}[{sel}={self}]".format(
            inst=instance_name, root=self.get_instance_root(instance_name),
            case=case_name, sel=self.selector, self=self
        ))

    @staticmethod
    def get_instance_root(instance_name):
        return {
            "results:inline": "results"
        }.get(instance_name, instance_name)


class CaseIDXPath(CaseSelectionXPath):
    selector = '@case_id'


class CaseTypeXpath(CaseSelectionXPath):
    selector = '@case_type'

    def case(self, instance_name='casedb', case_name='case'):
        quoted = CaseTypeXpath("'{}'".format(self))
        return super(CaseTypeXpath, quoted).case(instance_name, case_name)

    def cases(self, additional_types, instance_name='casedb', case_name='case'):
        quoted = CaseTypeXpath("'{}'".format(self))
        selector = "{sel}={quoted}".format(sel=self.selector, quoted=quoted)
        for type in additional_types:
            quoted = CaseTypeXpath("'{}'".format(type))
            selector = "{selector} or {sel}={quoted}".format(selector=selector, sel=self.selector, quoted=quoted)
        return CaseXPath("instance('{inst}')/{root}/{case}[{sel}]".format(
            inst=instance_name, root=self.get_instance_root(instance_name), case=case_name, sel=selector
        ))


class UsercaseXPath(XPath):

    def case(self):
        user_id = session_var(var='userid', path='context')
        return CaseTypeXpath(USERCASE_TYPE).case().select('hq_user_id', user_id)


class CaseXPath(XPath):

    def index_id(self, name):
        return CaseIDXPath(self.slash('index').slash(name))

    def parent_id(self):
        return self.index_id('parent')

    def property(self, property):
        return self.slash(property)


class LocationXpath(XPath):

    def location(self, ref, hierarchy):

        def gen_path(types):
            def _gen():
                for type in types:
                    yield '%ss' % type
                    yield type

            return '/'.join(_gen())

        def gen_expr(path):
            query = '[@id = current()/location_id]'
            if not path:
                return query
            else:
                return '[count({path}{query}) > 0]'.format(
                    path=gen_path(path),
                    query=query,
                )

        def ref_to_xpath(input, hierarchy):
            my_type, ref_type, property = self._parse_input(input)
            types = self._ordered_types(hierarchy)
            prefix_path = types[0:types.index(ref_type) + 1]
            prefix = gen_path(prefix_path)
            my_path = types[types.index(ref_type) + 1:types.index(my_type) + 1]
            my_expr = gen_expr(my_path)
            return '{prefix}{expr}/{property}'.format(prefix=prefix, expr=my_expr, property=property)

        self.validate(ref, hierarchy)
        return XPath("instance('{instance}')/{ref}").format(instance=self, ref=ref_to_xpath(ref, hierarchy))

    def validate(self, ref, hierarchy):
        my_type, ref_type, property = self._parse_input(ref)
        types = self._ordered_types(hierarchy)
        for type in [my_type, ref_type]:
            if type not in types:
                raise LocationXPathValidationError(
                    _('Type {type} must be in list of domain types: {list}').format(
                        type=type,
                        list=', '.join(types)
                    )
                )

        if types.index(ref_type) > types.index(my_type):
            raise LocationXPathValidationError(
                _('Reference type {ref} cannot be a child of primary type {main}.'.format(
                    ref=ref_type,
                    main=my_type,
                ))
            )

    def _parse_input(self, input):
        try:
            my_type, ref = input.split(':')
            ref_type, property = ref.split('/')
            return my_type, ref_type, property
        except ValueError:
            raise LocationXPathValidationError(_(
                'Property not correctly formatted. '
                'Must be formatted like: loacation:mytype:referencetype/property. '
                'For example: location:outlet:state/name'
            ))

    def _ordered_types(self, hierarchy):
        from corehq.apps.commtrack.util import unicode_slug

        def _gen(hierarchy):
            next_types = set([None])
            while next_types:
                next_type = next_types.pop()
                if next_type is not None:
                    yield next_type
                new_children = hierarchy.get(next_type, [])
                for child in new_children:
                    next_types.add(child)

        return [unicode_slug(t) for t in _gen(hierarchy)]


class CaseClaimXpath(object):
    def __init__(self, session_var_name):
        self.session_var_name = session_var_name

    def default_relevant(self):
        # Checks to see if the searched-for case already exists in the casedb:
        # count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0
        return CaseIDXPath(session_var(self.session_var_name)).case().count().eq(0)

    @classmethod
    def multi_case_relevant(cls):
        # Verifies that there's at least one case that isn't yet owned by the user
        return XPath("$case_id").neq(XPath.string(""))


class LedgerdbXpath(XPath):

    def ledger(self):
        entity_id_selection = CaseSelectionXPath(session_var(self))
        entity_id_selection.selector = '@entity-id'
        return LedgerXpath(entity_id_selection.case(instance_name='ledgerdb', case_name='ledger'))


class LedgerXpath(XPath):

    def section(self, section):
        return LedgerSectionXpath(self.slash('section').select('@section-id', section))


class LedgerSectionXpath(XPath):

    def entry(self, id):
        return XPath(self.slash('entry').select('@id', id, quote=False))


class InstanceXpath(XPath):
    id = ''
    path = ''

    def instance(self):
        return XPath("instance('{id}')/{path}".format(
            id=self.id,
            path=self.path)
        )


class SessionInstanceXpath(InstanceXpath):
    id = 'commcaresession'
    path = 'session/context'


class ItemListFixtureXpath(InstanceXpath):

    @property
    def id(self):
        return 'item-list:{}'.format(self)

    @property
    def path(self):
        return '{0}_list/{0}'.format(self)


class ProductInstanceXpath(InstanceXpath):
    id = 'commtrack:products'
    path = 'products/product'


class IndicatorXpath(InstanceXpath):
    path = 'indicators/case[@id = current()/@case_id]'

    @property
    def id(self):
        return self


class SearchSelectedCasesInstanceXpath(InstanceXpath):
    default_id = "search_selected_cases"
    path = "results/value"

    @property
    def id(self):
        return self or self.default_id


class LocationInstanceXpath(InstanceXpath):
    id = 'locations'
    path = 'locations/location'


class CommCareSession(object):
    username = SessionInstanceXpath().instance().slash("username")
    userid = SessionInstanceXpath().instance().slash("userid")


class ScheduleFixtureInstance(XPath):

    def visit(self):
        return XPath("instance('{0}')/schedule/visit".format(self))

    def expires(self):
        return XPath("instance('{0}')/schedule/@expires".format(self))

    def starts(self):
        return XPath("instance('{0}')/schedule/@starts".format(self))

    def unscheduled_visits(self):
        return XPath("instance('{0}')/schedule/@allow_unscheduled".format(self))


class ScheduleFormXPath(object):
    """
    XPath queries for scheduled forms
    """

    def __init__(self, form, phase, module):
        self.form = form
        self.phase = phase
        self.module = module

        try:
            self.phase.anchor
        except AttributeError:
            raise ScheduleError("Phase needs an Anchor")

        self.anchor_detail_variable_name = "anchor_{}".format(self.form.schedule_form_id)
        self.last_visit_detail_variable_name = SCHEDULE_LAST_VISIT.format(self.form.schedule_form_id)
        self.last_visit_date_detail_variable_name = SCHEDULE_LAST_VISIT_DATE.format(self.form.schedule_form_id)

        self.anchor = "${}".format(self.anchor_detail_variable_name)
        self.last_visit = "${}".format(self.last_visit_detail_variable_name)
        self.last_visit_date = "${}".format(self.last_visit_date_detail_variable_name)
        self.date_opened = "${}".format(SCHEDULE_DATE_CASE_OPENED)
        self.current_schedule_phase = SCHEDULE_PHASE

    @property
    def fixture_id(self):
        from corehq.apps.app_manager import id_strings
        return id_strings.schedule_fixture(self.module, self.phase, self.form)

    @property
    def fixture(self):
        return ScheduleFixtureInstance(self.fixture_id)

    @property
    def xpath_phase_set(self):
        """
        returns the due date if there are valid upcoming schedules
        otherwise, returns a Really Big Number
        """
        return XPath.if_(self.next_valid_schedules(include_beginning_of_relevancy_window=False),
                         self.due_date(), SCHEDULE_MAX_DATE)

    @property
    def first_visit_phase_set(self):
        """
        returns the first due date if the case hasn't been visited yet.
        """
        within_zeroth_phase = XPath.and_(
            XPath(self.current_schedule_phase).eq(XPath.string('')),  # No visits yet
            XPath(self.anchor).neq(XPath.string('')),
            self.within_form_relevancy(),
        )

        return XPath.if_(
            within_zeroth_phase,
            self.first_due_date(),
            self.xpath_phase_set
        )

    @property
    def next_visit_due_num(self):
        phase = self.phase.id
        return XPath.if_(self.next_valid_schedules(phase), self.next_visit_id(), 0)

    @property
    def is_unscheduled_visit(self):
        """count(visit[within_window][@id != coalesce(last_visit_number_{form_id},0)]) = 0"""
        last_visit_id = XPath('@id != {}'.format("coalesce({}, {})".format(self.last_visit, 0)))
        count = XPath.count(
            self.fixture.visit().select_raw(self.within_window()).
            select_raw(last_visit_id)
        )
        return XPath("{} = 0".format(count))

    @staticmethod
    def next_visit_date(last_visit_dates):
        """
        Returns the next visit date given all the last visits
        if($next_visit_date < today() and (current_schedule_phase = '' or last_visit_date_{all_forms} = ''),
            $date_case_opened,
            $next_visit_date)
        """
        # (last_visit_f1 = '' and last_visit_f2 = '' and ...)
        no_visits = XPath.and_(*["${} = ''".format(last_visit)
                                 for last_visit in last_visit_dates])

        use_date_opened = XPath.and_(
            XPath("${} < today()".format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE)),
            XPath.or_(
                XPath(SCHEDULE_PHASE).eq(XPath.string('')),
                no_visits
            )
        )
        return XPath.if_(
            use_date_opened,
            "${}".format(SCHEDULE_DATE_CASE_OPENED),
            "${}".format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE),
        )

    def filter_condition(self, phase_id):
        """returns the `relevant` condition on whether to show this form in the list"""
        next_valid_schedules = self.next_valid_schedules(phase_id)
        visit_allowed = self.visit_allowed()
        return XPath.and_(next_valid_schedules, visit_allowed)

    def current_schedule_phase_calculation(self, termination_condition, transition_condition):
        """
        Returns the current schedule phase calculation, taking transition and termination conditions into account.

        if({termination_condition}, '-1',
            if({transition_condition}, current_form_phase + 1, current_form_phase))
        """
        this_phase = self.phase.id
        next_phase = this_phase + 1

        return XPath.if_(
            termination_condition,
            SCHEDULE_TERMINATED,
            XPath.if_(
                transition_condition,
                str(next_phase),
                str(this_phase),
            ),
        )

    def within_form_relevancy(self):
        """
        (today() >= date({anchor}) + int({schedule}/@starts)
        and (today <= date{anchor} + int({schedule}/@expires) or {schedule}/@expires = ''))
        """
        starts = self.fixture.starts()

        return XPath.and_(
            XPath("today() >= ({} + {})".format(XPath.date(self.anchor), XPath.int(starts))),
            self.before_form_relevancy_expires()
        )

    def before_form_relevancy_expires(self):
        """(today <= date{anchor} + int({schedule}/@expires) or {schedule}/@expires = '')"""
        expires = self.fixture.expires()
        return XPath.or_(
            XPath(expires).eq(XPath.string('')),
            "today() <= ({} + {})".format(XPath.date(self.anchor), XPath.int(expires))
        )

    def next_valid_schedules(self, phase_id=None, include_beginning_of_relevancy_window=True):
        """
        [current_schedule_phase = '' or ]current_schedule_phase = phase.id and
        {anchor} != '' and
        {within_form_relevancy_window} | {before_form_relevancy_expires}

        include_beginning_of_relevancy_window option either takes into account the form relevancy window
        """

        current_phase_query = XPath(self.current_schedule_phase).eq(self.phase.id)
        if phase_id == 1:
            # No visits yet
            zeroth_phase = XPath(self.current_schedule_phase).eq(XPath.string(''))
            current_phase_query = XPath.or_(zeroth_phase, current_phase_query)

        valid_within_window = XPath.and_(
            current_phase_query,
            XPath(self.anchor).neq(XPath.string('')),
            (self.within_form_relevancy() if include_beginning_of_relevancy_window
             else self.before_form_relevancy_expires()),
        )

        return valid_within_window

    def before_window(self):
        """
        if(@repeats = 'True',
             (@expires = '' or today() <= date(last_visit_date{form_id}) + int(@increment) + int(@expires)),
             (@expires = '' or today() <= date({anchor}) + int(@due) + int(@expires))
        )
        """
        before_repeat = XPath.or_(
            XPath('@expires').eq(XPath.string('')),
            XPath('today() <= ({} + {} + {})'.format(
                XPath.date(self.last_visit_date),
                XPath.int('@increment'),
                XPath.int('@expires'))
            )
        )
        before_standard = XPath.or_(
            XPath('@expires').eq(XPath.string('')),
            XPath('today() <= ({} + {} + {})'.format(
                XPath.date(self.anchor),
                XPath.int('@due'),
                XPath.int('@expires'))
            )
        )
        return XPath.if_(
            "@repeats = 'True'",
            before_repeat,
            before_standard,
        )

    def within_window(self):
        """
        if(@repeats = 'True',
            today() >= date(last_visit_date_{form_id}) + int(@increment) + int(@starts) and
                 (@expires = '' or today() <= date(last_visit_date{form_id}) + int(@increment) + int(@expires)),
            today() >= date({anchor}) + int(@due) + int(@starts) and
                 (@expires = '' or today() <= date({anchor}) + int(@due) + int(@expires))
        )
        """
        within_repeat = XPath.and_(
            XPath('today() >= ({} + {} + {})'.format(
                XPath.date(self.last_visit_date),
                XPath.int('@increment'),
                XPath.int('@starts'),
            )),
            XPath.or_(
                XPath('@expires').eq(XPath.string('')),
                XPath('today() <= ({} + {} + {})'.format(
                    XPath.date(self.last_visit_date),
                    XPath.int('@increment'),
                    XPath.int('@expires'))
                )
            )
        )
        within_standard = XPath.and_(
            XPath('today() >= ({} + {} + {})'.format(
                XPath.date(self.anchor),
                XPath.int('@due'),
                XPath.int('@starts'),
            )),
            XPath.or_(
                XPath('@expires').eq(XPath.string('')),
                XPath('today() <= ({} + {} + {})'.format(
                    XPath.date(self.anchor),
                    XPath.int('@due'),
                    XPath.int('@expires'))
                )
            )
        )
        return XPath.if_(
            "@repeats = 'True'",
            within_repeat,
            within_standard,
        )

    def next_visits(self):
        """last_visit_num_{form_unique_id} = '' or if(@repeats = 'True',
        @id >= last_visit_num_{form_unique_id}, @id > last_visit_num_{form_unique_id}
        """
        last_visit_repeat = XPath('@id >= {}'.format(self.last_visit))
        last_visit_no_repeat = XPath('@id > {}'.format(self.last_visit))
        next_visits = "if(@repeats = 'True', {}, {})".format(last_visit_repeat, last_visit_no_repeat)
        first_visit = XPath("{} = ''".format(self.last_visit))

        return XPath.or_(first_visit, next_visits)

    def upcoming_scheduled_visits(self):
        """instance(...)/schedule/visit/[next_visits][within_window]"""
        return (self.fixture.
                visit().
                select_raw(self.next_visits()).
                select_raw(self.within_window()))

    def visit_allowed(self):
        """
        {schedule}/@allow_unscheduled = 'True' or
        count({upcoming_scheduled_visits} > 0)
        """
        num_upcoming_visits = XPath.count(self.upcoming_scheduled_visits())
        num_upcoming_visits_gt_0 = XPath('{} > 0'.format(num_upcoming_visits))
        return XPath.or_(
            XPath("{} = 'True'".format(self.fixture.unscheduled_visits())),
            num_upcoming_visits_gt_0
        )

    def due_first(self):
        """instance(...)/schedule/visit[before_window][1]/@due"""
        # Only uses @due since we can't have a repeat visit on the first visit
        due = self.fixture.visit().select_raw(self.before_window()).select_raw("1").slash("@due")
        return "coalesce({}, {} - {})".format(due, SCHEDULE_MAX_DATE, XPath.date(self.anchor))

    def due_later(self):
        """if(visit/[next_visits][before_window][1]/@increment != '', @increment + last_visit_date_{form_id},
              visit/[next_visits][before_window][1]/@due != '', @due + anchor_date, MAX_DATE)
        """
        due_visit = (self.fixture.visit().
                     select_raw(self.next_visits()).
                     select_raw(self.before_window()).
                     select_raw("1"))
        due_repeat = due_visit.slash("@increment")
        due_regular = due_visit.slash("@due")
        due = (
            "if({repeat} != '', {repeat} + date({last_visit}),"
            " if({regular} != '', {regular} + date({anchor}),"
            " {max_date}))".format(
                repeat=due_repeat,
                last_visit=self.last_visit_date,
                regular=due_regular,
                anchor=self.anchor,
                max_date=SCHEDULE_MAX_DATE,)
        )
        return due

    def next_visit_id(self):
        """{visit}/[next_visits][within_window][1]/@id"""
        return (self.upcoming_scheduled_visits().
                select_raw("1").
                slash("@id"))

    def first_due_date(self):
        return "{} + {}".format(XPath.date(self.anchor), XPath.int(self.due_first()))

    def due_date(self):
        return "coalesce({}, {})".format(self.due_later(), SCHEDULE_MAX_DATE)


class QualifiedScheduleFormXPath(ScheduleFormXPath):
    """
    Fully Qualified XPath queries for scheduled forms

    Instead of raw case properties, this fetches the properties from the casedb
    """

    def __init__(self, form, phase, module, case_xpath):
        super(QualifiedScheduleFormXPath, self).__init__(form, phase, module)
        self.case_xpath = case_xpath
        self.last_visit = self.case_xpath.slash(SCHEDULE_LAST_VISIT.format(self.form.schedule_form_id))
        self.last_visit_date = self.case_xpath.slash(SCHEDULE_LAST_VISIT_DATE).format(self.form.schedule_form_id)
        self.anchor = self.case_xpath.slash(self.phase.anchor)
        self.current_schedule_phase = self.case_xpath.slash(SCHEDULE_PHASE)

    @staticmethod
    def next_visit_date(forms, case_xpath):
        """
        Returns the next visit date given all the last visits
        if($next_visit_date < today() and (current_schedule_phase = '' or last_visit_date_{all_forms} = ''),
            $date_case_opened,
            $next_due_visit)
        """
        last_visit_dates = [case_xpath.slash(SCHEDULE_LAST_VISIT_DATE).format(form.schedule_form_id)
                            for form in forms]
        # (last_visit_f1 = '' and last_visit_f2 = '' and ...)
        no_visits = XPath.and_(*["{} = ''".format(last_visit)
                                 for last_visit in last_visit_dates])

        use_date_opened = XPath.and_(
            XPath("/data/{} < today()".format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE)),
            XPath.or_(
                XPath(case_xpath.slash(SCHEDULE_PHASE)).eq(XPath.string('')),
                no_visits
            )
        )
        return XPath.if_(
            use_date_opened,
            case_xpath.slash(SCHEDULE_DATE_CASE_OPENED),
            "/data/{}".format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE),
        )
