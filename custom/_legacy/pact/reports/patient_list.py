from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.users.models import CommCareUser
from pact.enums import PACT_DOMAIN, PACT_HP_CHOICES, PACT_DOT_CHOICES


class PactPrimaryHPField(BaseSingleOptionFilter):
    slug = "primary_hp"
    label = "PACT HPs"
    default_text = "All CHWs"

    @property
    def options(self):
        chws = list(self.get_chws())
        return [(c['val'], c['text']) for c in chws]

    @classmethod
    def get_chws(cls):
        users = CommCareUser.by_domain(PACT_DOMAIN)
        for x in users:
            #yield dict(val=x._id, text=x.raw_username)
            yield dict(val=x.raw_username, text=x.raw_username)
#        self.options = [dict(val=case['_id'], text="(%s) - %s" % (case['pactid'], case['name'])) for case in patient_cases]
