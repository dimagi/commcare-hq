from collections import namedtuple, defaultdict
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.models import Form
from corehq.apps.performance_sms.exceptions import QueryResolutionError, MissingTemplateError
from corehq.apps.performance_sms.parser import GLOBAL_NAMESPACE, USER_NAMESPACE, GROUP_NAMESPACE
from corehq.apps.reports.daterange import get_daterange_start_end_dates
from corehq.apps.sofabed.models import FormData
from dimagi.utils.decorators.memoized import memoized


QueryContext = namedtuple('MessageContext', ['user', 'group', 'template_vars'])


class Resolver(object):

    def resolve(self, variable, context):
        raise NotImplementedError()


class UserResolver(Resolver):

    def resolve(self, variable, context):
        try:
            return getattr(context.user, variable)
        except AttributeError:
            raise QueryResolutionError(_("Couldn't resolve variable {}").format(variable))


class GroupResolver(Resolver):

    def resolve(self, variable, context):
        try:
            return getattr(context.group, variable)
        except AttributeError:
            raise QueryResolutionError(_("Couldn't resolve variable {}").format(variable))


class TemplateResolver(Resolver):

    def resolve(self, variable, context):

        return variable


class QueryEngine(object):

    def __init__(self, template_vars):
        self.template_vars = template_vars
        self.resolvers = {
            GLOBAL_NAMESPACE: TemplateResolver(),
            USER_NAMESPACE: UserResolver(),
            GROUP_NAMESPACE: GroupResolver(),
        }

    @memoized
    def get_template_variable(self, slug):
        matches = filter(lambda var: var.slug==slug, self.template_vars)
        if len(matches) == 1:
            return matches[0]
        else:
            raise MissingTemplateError(_("Couldn't match with slug {}").format(slug))

    def get_context(self, params, query_context):

        # this is to support string formatting dot notation. there is probably a better way to do this
        class Params(object):
            pass

        context = defaultdict(Params)
        for param in params:
            value = self.resolve(param, query_context)
            if param.namespace == GLOBAL_NAMESPACE:
                context[param.variable] = value
            else:
                setattr(context[param.namespace], param.variable, value)
        return context

    def resolve(self, param, query_context):
        if param.namespace == GLOBAL_NAMESPACE:
            template_varaible = self.get_template_variable(slug=param.variable)
            return self._resolve_from_template(template_varaible, query_context)
        try:
            return self.resolvers[param.namespace].resolve(param.variable, query_context)
        except QueryResolutionError:
            # todo: we may want to log / notify these
            return _('[unknown]')

    def _resolve_from_template(self, template, query_context):
        # todo: support other types and options
        assert template.type == 'form'
        startdate, enddate = get_daterange_start_end_dates(template.time_range)
        xmlns = Form.get_form(template.source_id).xmlns
        return FormData.objects.filter(
            user_id=query_context.user._id,
            xmlns=xmlns,
            received_on__gte=startdate,
            received_on__lt=enddate,
        ).count()
