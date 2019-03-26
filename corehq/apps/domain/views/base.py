from __future__ import absolute_import, unicode_literals

import itertools
from datetime import date, timedelta

from django.utils.decorators import method_decorator
from django.urls import reverse
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import ugettext as _

from corehq.apps.accounting.models import CreditLine, Subscription
from corehq.apps.accounting.utils import months_from_date
from corehq.apps.hqwebapp.utils import get_overdue_invoice
from corehq.apps.users.models import Invitation
from corehq.apps.domain.decorators import login_required, login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.views import BaseSectionPageView
from memoized import memoized


# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, domain_select_template='domain/select.html', do_not_redirect=False):
    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')

    email = request.couch_user.get_email()
    open_invitations = [e for e in Invitation.by_email(email) if not e.is_expired]

    additional_context = {
        'domains_for_user': domains_for_user,
        'open_invitations': open_invitations,
        'current_page': {'page_name': _('Select A Project')},
    }

    last_visited_domain = request.session.get('last_visited_domain')
    if open_invitations \
       or do_not_redirect \
       or not last_visited_domain:
        return render(request, domain_select_template, additional_context)
    else:
        domain_obj = Domain.get_by_name(last_visited_domain)
        if domain_obj and domain_obj.is_active:
            # mirrors logic in login_and_domain_required
            if (
                request.couch_user.is_member_of(domain_obj)
                or (request.user.is_superuser and not domain_obj.restrict_superusers)
                or domain_obj.is_snapshot
            ):
                try:
                    from corehq.apps.dashboard.views import dashboard_default
                    return dashboard_default(request, last_visited_domain)
                except Http404:
                    pass

        del request.session['last_visited_domain']
        return render(request, domain_select_template, additional_context)


class DomainViewMixin(object):
    """
        Paving the way for a world of entirely class-based views.
        Let's do this, guys. :-)

        Set strict_domain_fetching to True in subclasses to bypass the cache.
    """
    strict_domain_fetching = False

    @property
    @memoized
    def domain(self):
        domain = self.args[0] if len(self.args) > 0 else self.kwargs.get('domain', "")
        return normalize_domain_name(domain)

    @property
    @memoized
    def domain_object(self):
        domain_obj = Domain.get_by_name(self.domain, strict=self.strict_domain_fetching)
        if not domain_obj:
            raise Http404()
        return domain_obj


class LoginAndDomainMixin(object):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


class BaseDomainView(LoginAndDomainMixin, BaseSectionPageView, DomainViewMixin):

    @property
    def main_context(self):
        main_context = super(BaseDomainView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        overdue_invoice = get_overdue_invoice(self.domain)
        main_context['domain_has_overdue_invoice'] = overdue_invoice is not None
        if overdue_invoice:
            days_overdue = (date.today() - overdue_invoice.date_due).days
            main_context['invoice_month'] = overdue_invoice.date_start.strftime('%B %Y')
            main_context['days_until_downgrade'] = max(1, 61 - days_overdue)

        context = main_context
        current_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if current_subscription:
            monthly_fee = current_subscription.plan_version.product_rate.monthly_fee
            if monthly_fee:
                prepaid_credits = sum([
                    credit_line.balance for credit_line in itertools.chain(
                        CreditLine.get_credits_by_subscription_and_features(current_subscription),
                        CreditLine.get_credits_by_subscription_and_features(current_subscription, is_product=True)
                        # TODO possibly add more sources of credit
                    )
                ])
                num_months_remaining = prepaid_credits / monthly_fee
                prepaid_remaining_date = months_from_date(date.today(), num_months_remaining)
                partial_month_remaining = num_months_remaining % 1
                num_days_in_month = 30  # TODO
                prepaid_remaining_date += timedelta(days=int(partial_month_remaining * num_days_in_month))
                prepaid_days_remaining = (prepaid_remaining_date - date.today()).days
                if prepaid_days_remaining > 0:
                    context['show_prepaid_modal'] = True
                    context['prepaid_days_remaining'] = prepaid_days_remaining
                    context['prepaid_weeks_remaining'] = max(prepaid_days_remaining // 7, 1)
                    context['monthly_fee'] = monthly_fee
                    context['plan_name'] = current_subscription.plan_version.plan.name
                    context['prepaid_remaining_date'] = prepaid_remaining_date
        return main_context

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])
