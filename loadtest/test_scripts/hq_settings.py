import mechanize
import cookielib


BASE_URL = 'https://staging.commcarehq.org'
DOMAIN = "demo"
USERNAME = "changeme@dimagi.com"
PASSWORD = "***"
MOBILE_USERNAME = "user@demo.commcarehq.org"
MOBILE_PASSWORD = "***"

# set the following two to use a different user for OTA restore
OTA_USERNAME = None
OTA_PASSWORD = None

try:
    from localsettings import *
except ImportError:
    pass

def login_url():
    return "%s%s" % (BASE_URL, "/accounts/login/")

# this is necessary to make the runner happy
class Transaction(object):
    def run(self): return

class HQTransaction(object):
    """
    Stick some shared stuff in here so we can use it across tests
    and keep most of the config in one place.
    """

    def __init__(self):
        self.custom_timers = {}
        self.base_url = BASE_URL
        self.domain = DOMAIN
        self.username = USERNAME
        self.password = PASSWORD
        self.submissions_username = MOBILE_USERNAME
        self.submissions_password = MOBILE_PASSWORD
        self.ota_username = (OTA_USERNAME if OTA_USERNAME is not None
                else MOBILE_USERNAME)
        self.ota_password = (OTA_PASSWORD if OTA_PASSWORD is not None
                else MOBILE_PASSWORD)

class User(object):
    def __init__(self, username, password, browser):
        self.username = username
        self.password = password
        self.browser = browser
        self.logged_in = False

    def ensure_logged_in(self):
        if not self.logged_in:
            _login(self.browser, self.username, self.password)
            self.logged_in = True

    def __str__(self):
        return "User<user=%s,logged_in=%s>" % (self.username, self.logged_in)

# utility functions
def init_browser():
    """Returns an initialized browser and associated cookie jar."""
    br = mechanize.Browser()
    cj = cookielib.LWPCookieJar()
    br.set_cookiejar(cj)

    br.set_handle_equiv(True)
    br.set_handle_gzip(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)

    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)
    return br

def _login(browser, username, password):
    _ = browser.open(login_url())
    browser.select_form(name="form")
    browser.form['username'] = username
    browser.form['password'] = password
    browser.submit()
