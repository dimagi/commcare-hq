import time
from hq_settings import init_browser, HQTransaction

class Transaction(HQTransaction):

    def run(self):
        br = init_browser()
        url = "%s/a/%s/phone/restore/" % (self.base_url, self.domain)
        start_timer = time.time()
        br.add_password(url, self.ota_username, self.ota_password)
        resp = br.open(url)
        latency = time.time() - start_timer
        self.custom_timers['ota-restore'] = latency
        body = resp.read()
        assert resp.code == 200, 'Bad HTTP Response'
        assert "Successfully restored" in body


if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
