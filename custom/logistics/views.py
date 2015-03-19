import json
from corehq import toggles
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.domain.decorators import cls_require_superuser_or_developer
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import ReportRun
from custom.logistics.models import MigrationCheckpoint, StockDataCheckpoint


class BaseConfigView(BaseCommTrackManageView):

    @cls_require_superuser_or_developer
    def dispatch(self, request, *args, **kwargs):
        return super(BaseConfigView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        try:
            checkpoint = MigrationCheckpoint.objects.get(domain=self.domain)
        except MigrationCheckpoint.DoesNotExist:
            checkpoint = None

        try:
            runner = ReportRun.objects.get(domain=self.domain, complete=False)
        except ReportRun.DoesNotExist:
            runner = None

        try:
            stock_data_checkpoint = StockDataCheckpoint.objects.get(domain=self.domain)
        except StockDataCheckpoint.DoesNotExist, StockDataCheckpoint.MultipleObjectsReturned:
            stock_data_checkpoint = None

        return {
            'stock_data_checkpoint': stock_data_checkpoint,
            'runner': runner,
            'checkpoint': checkpoint,
            'settings': self.settings_context,
            'source': self.source,
            'sync_url': self.sync_urlname,
            'sync_stock_url': self.sync_stock_url,
            'clear_stock_url': self.clear_stock_url,
            'is_developer': toggles.IS_DEVELOPER.enabled(self.request.couch_user.username),
            'is_commtrack_enabled': CommtrackConfig.for_domain(self.domain)
        }

    @property
    def settings_context(self):
        config = self.config.for_domain(self.domain_object.name)
        if config:
            return {
                "source_config": config._doc,
            }
        else:
            return {
                "source_config": self.config()._doc
            }

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))
        config = self.config.wrap(self.settings_context['source_config'])
        config.enabled = payload['source_config'].get('enabled', None)
        config.domain = self.domain_object.name
        config.url = payload['source_config'].get('url', None)
        config.username = payload['source_config'].get('username', None)
        config.password = payload['source_config'].get('password', None)
        config.steady_sync = payload['source_config'].get('steady_sync')
        config.save()
        return self.get(request, *args, **kwargs)


class BaseRemindersTester(BaseDomainView):
    section_name = 'Reminders tester'
    section_url = ""
    template_name = "logistics/reminders_tester.html"
    post_url = None

    reminders = {}

    def get_context_data(self, **kwargs):
        context = super(BaseRemindersTester, self).get_context_data(**kwargs)
        context['phone_number'] = kwargs.get('phone_number')
        verified_number = VerifiedNumber.by_phone(context['phone_number'])
        context['phone_user'] = CommCareUser.get(verified_number.owner_id) if verified_number else None
        return context

    @property
    def main_context(self):
        main_context = super(BaseRemindersTester, self).main_context
        main_context.update({
            'reminders': sorted(self.reminders.keys()),
            'post_url': self.post_url
        })
        return main_context
