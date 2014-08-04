from django.utils.translation import ugettext_noop as _
from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport
from casexml.apps.case.models import CommCareCase

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        AdoptionBarChartReport,
    )),
)

from django.db.models import signals
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.pillow import ConfigurableIndicatorPillow
from corehq.apps.userreports.sql import rebuild_table
from custom.care_pathways.utils import get_domain_configuration


def create_pillows(app, **kwargs):
    app_name = app.__name__.rsplit('.', 1)[0]
    if app_name == 'custom.care_pathways':
        for domain in ('pathways-india-mis', 'pathways-tanzania',):
            main_config = get_domain_configuration(domain)
            config = IndicatorConfiguration.wrap(main_config['pillow_config'])
            pillow = ConfigurableIndicatorPillow(config)
            rebuild_table(pillow._table)
            for i, row in enumerate(CommCareCase.get_all_cases(domain)):
                print "\tProcessing item %s (%d)" % (row['id'], i)
                pillow.change_transport(row)


signals.post_syncdb.connect(create_pillows)