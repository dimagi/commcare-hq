import mechanize
import time
from hq_settings import init_browser, User, HQTransaction

class Transaction(HQTransaction):

    def run(self):
        br = init_browser()
        start_timer = time.time()
        user = User(self.username, self.password, br)
        user.ensure_logged_in()
        latency = time.time() - start_timer
        self.custom_timers['Login'] = latency

        resp = br.open('%s/a/%s/reports/' % (self.base_url, self.domain))
        body = resp.read()
        assert resp.code == 200, 'Bad HTTP Response'
        assert "Case Activity" in body, "Couldn't find report list"


if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
