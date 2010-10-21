import logging

# this is utility code for retrying an unreliable operation
# (network access, db access, etc.) several times before giving
# up. useful for remote scripts that you want to make super-
# robust.

def retry_task (task, retry_sched):
    """execute a task, retrying the task a fixed number of times until success
  
    the task is encapsulated in the 'task' object; see the *Task classes. the max number of retries
    and delays between them is determined by the retry_sched param, a list of retry_delays in seconds"""
    success = False
    tries = 0
    total_tries = len(retry_sched) + 1

    while not success and tries < total_tries:
        try:
            success = task.do()
        except:
            logging.warning('task.do() threw an exception; this is not allowed')
            raise
        tries += 1
    
    if not success:
        if tries < total_tries:
            retry_wait = retry_sched[tries - 1]
            task.hook_fail_retry(tries, total_tries, retry_wait)
            time.sleep(retry_wait)
        else:
            task.hook_fail(total_tries)
    else:
        task.hook_success(tries, total_tries)

    return (success, task.result(success))

# retry_task(MyTask(), [0, 30, 60])
#
# this will attempt MyTask until it succeeds, up to four times
# after the first failure it re-attempts immediately, then waits
# 30 seconds before the next attempt, then 60, then gives up

"""
class Task:
    def do:
        execute the task at hand; return True if successful, False if not; it is do()'s responsibility
        to handle all exceptions; it must NEVER throw an exception

    def hook_success (tries, total_tries):
        called if task is successful; tries is the attempt # that succeeded, total_tries the max # of
        attempts that would have been allowed

    def hook_fail (total_tries):
        called if the task is unsuccessful after exhausting all attempts
      
    def hook_fail_retry (tries, total_tries, retry_wait):
        called if the taks is unsuccessful on a given attempt, and another run will be attempted; tries
        is the attempt # that just failed, retry_wait is the delay in second before the next attempt
      
    def result (success):
        return the result of the task; success is whether execution was successful (note: this result will
        usually have to be cached in a class variable in do()
"""

################
### EXAMPLES ###
################

class GetUnsyncedRecordsTask:
    """retryable task for pulling the set of records to sync from the staging database"""

    def do (self):
        try:
            self.records = get_unsynced_records()
            return True
        except:
            log.exception('could not read records to sync from staging database')
            return False

    def hook_success (self, tries, total_tries):
        if tries > 1:
            log.info('successfully read records to sync on attempt %d' % tries)
  
    def hook_fail (self, total_tries):
        log.info('could not read records to sync; no records will be sent in this payload')
  
    def hook_fail_retry (self, tries, total_tries, retry_wait):
        pass
    
    def result (self, success):
        return self.records if success else []

class SendAllTask:
    """task manager for sending N payloads, allowing a certain number of retries"""
    def __init__ (self, payloads):
        self.payloads = payloads
        self.i = 0
  
    def do (self):
        while self.i < len(self.payloads):
            success = send_payload(self.payloads[self.i])
            #note: send_payload handles all exceptions
            if success:
                self.i += 1
                logging.info('sent payload %d of %d' % (self.i, len(self.payloads)))
            else:
                return False
        return True
    
    def hook_success (self, tries, total_tries):
        log.info('sync successful')
    
    def hook_fail (self, total_tries):
        log.warning('too many failed send attempts; aborting send; %d of %d payloads successfully transmitted' % (self.i, len(self.payloads)))
    
    def hook_fail_retry (self, tries, total_tries, retry_wait):
        log.warning('failed send on payload %d of %d; %d tries left; resuming in %d seconds' % (self.i + 1, len(self.payloads), total_tries - tries, retry_wait))
    
    def result (self, success):
        return None

class WebServiceTask:
    def __init__(self, url, post_process_func=lambda x: (False, x), timeout=15.):
        self.url = url
        self.postproc = post_process_func
        self.timeout = timeout
        self.value = None
        self.errors = []
        
    def do(self):
        try:
            f = urllib2.urlopen(self.url, timeout=self.timeout)
            data = f.read()

            try_again, val = self.postproc(data)
            if try_again:
                raise ValueError(val)

            self.value = val
            return True
        except Exception, e:
            self.errors.append(e)
            return False

    def hook_success(self, tries, total_tries):
        pass
  
    def hook_fail(self, total_tries):
        pass

    def hook_fail_retry(self, tries, total_tries, retry_wait):
        pass
    
    def result(self, success):
        return self.value if success else self.errors
