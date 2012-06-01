import mechanize
import time
from hq_settings import HQTransaction

class Transaction(HQTransaction):
    
    def run(self):
        br = mechanize.Browser()
        br.set_handle_robots(False)
        start_timer = time.time()
        resp = br.open(self.base_url + '/home/')
        resp.read()
        latency = time.time() - start_timer
        self.custom_timers['Public_Landing_Page'] = latency  
        assert (resp.code == 200), 'Bad HTTP Response'
        

if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
