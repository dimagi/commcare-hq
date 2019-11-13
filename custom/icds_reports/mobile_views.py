from corehq.apps.hqwebapp import views as hqwebapp_views


def login(req, domain):
    return hqwebapp_views.domain_login(req, domain, custom_template_name='icds_reports/mobile_login.html')
