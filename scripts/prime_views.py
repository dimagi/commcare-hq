
from couchforms.models import XFormInstance

def run():
    views = [
        'formtrends/form_duration_by_user',
        'groupexport/by_domain',
        'submituserlist/all_users',
        'reports/all_submissions',
        'couchexport/schema_index',
        'adm/all_default_columns',
        'app_manager/applications',
        'appstore/by_app',
        'auditcare/login_events',
        'builds/all',
        'case/all_cases',
        'cleanup/submissions',
        'cloudcare/cloudcare_apps',
        'couchforms/by_user',
        'dca/dca_collection_forms',
        'fixtures/data_items_by_domain_type',
        'hqbilling/tax_rates',
        'hqcase/all_case_properties',
        'groupexport/by_domain',
        'domain/snapshots',
        'hsph/cases_by_birth_date',
        'mvp/household_visits',
        'orgs/by_name',
        'pathindia/kranti_report',
        'phone/cases_sent_to_chws',
        'phonelog/devicelog_data',
        'pathfinder/pathfinder_all_wards',
        'prescriptions/all',
        'receiverwrapper/all_submissions_by_domain',
        'registration/requests_by_username',
        'reminders/by_domain_handler_case',
        'reports/weekly_notifications',
        'sms/verified_number_by_suffix',
        'translations/popularity',
        'users/admins_by_domain',
    ]

    def do_prime(view_name):
        print "priming %s" % view_name
        try:
            db = XFormInstance.get_db()
            db.view(view_name, limit=2).all()
        except:
            print "Got an exception but ignoring"

    from gevent import monkey; monkey.patch_all(thread=False)
    from gevent.pool import Pool
    import time
    pool = Pool(12)
    while True:
        for view in views:
            g = pool.spawn(do_prime, view)
        pool.join()
        print "Finished priming views, waiting 30 seconds"
        time.sleep(30)

    print "done!"

