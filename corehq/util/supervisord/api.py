import xmlrpclib
from amqplib.client_0_8.method_framing import defaultdict
from django.conf import settings
from jsonobject.api import JsonObject
from jsonobject.properties import StringProperty, IntegerProperty
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception

SERVER_STATE_RUNNING = 1

FAULT_NOT_RUNNING = 70


class SupervisorException(Exception):
    pass


class ProcessInfo(JsonObject):
    host = StringProperty()  # not in the API
    name = StringProperty()
    group = StringProperty()
    start = IntegerProperty()
    stop = IntegerProperty()
    now = IntegerProperty()
    state = IntegerProperty()
    statename = StringProperty()
    spawnerr = StringProperty()
    exitstatus = IntegerProperty()
    stdout_logfile = StringProperty()
    stderr_logfile = StringProperty()
    pid = IntegerProperty()


def wrap_exception():
    def decorate(func):
        def call_function(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except SupervisorException:
                raise
            except Exception as e:
                message = "Supervisor RPC call failed '{}' failed: ".format(func.__name__)
                notify_exception(None, message)
                raise SupervisorException(message, e)
        return call_function
    return decorate


class SupervisorApi(object):
    """
    Thin wrapper around the Supervisord XML-RPC interface
    http://supervisord.org/api.html
    """

    def __init__(self, host):
        if not settings.SUPERVISOR_RPC_ENABLED:
            raise SupervisorException('Supervisord RPC interface not enabled in '
                            'this environment: {}'.format(settings.SERVER_ENVIRONMENT))
        self._url = 'http://{username}:{password}@{host}:9001/RPC2'.format(
            username=settings.SUPERVISOR_USERNAME,
            password=settings.SUPERVISOR_PASSWORD,
            host=host
        )
        self._server = xmlrpclib.Server(self._url)
        self.check_state()

    @wrap_exception()
    def check_state(self):
        state = self._server.supervisor.getState()
        if state['statecode'] != SERVER_STATE_RUNNING:
            raise SupervisorException('Supervisord is not running: {}'.format(state['statename']))

    @wrap_exception()
    def get_all_process_info(self):
        return [ProcessInfo.wrap(info) for info in self._server.supervisor.getAllProcessInfo()]

    @wrap_exception()
    def get_process_info(self, name):
        return ProcessInfo.wrap(self._server.supervisor.getProcessInfo(name))

    @wrap_exception()
    def start_process(self, name, wait=True):
        return self._server.supervisor.startProcess(name, wait)

    @wrap_exception()
    def stop_process(self, name, wait=True):
        try:
            return self._server.supervisor.stopProcess(name, wait)
        except xmlrpclib.Fault as f:
            if f.faultCode == FAULT_NOT_RUNNING:
                return True
            else:
                raise

    @wrap_exception()
    def restart_process(self, name, wait=True):
        return self.stop_process(name, wait) and self.start_process(name, wait)


class HQSupervisorApi(object):

    def __init__(self, inventory_group):
        self.inventory_group = inventory_group
        self.servers = {
            host: SupervisorApi(host)
            for host in settings.ENVIRONMENT_HOSTS[inventory_group]
        }

    @staticmethod
    def _add_host(process_info, host):
        process_info.host = host
        return process_info

    @memoized
    def get_all_process_info(self):
        return [
            HQSupervisorApi._add_host(process_info, host)
            for host, server in self.servers.items()
            for process_info in server.get_all_process_info()
        ]

    def refresh_process_infos(self):
        self.get_all_process_info.reset_cache(self)
        self.get_all_process_info()

    def _process_info_by_host_name(self):
        mapping = defaultdict(defaultdict)
        for info in self._get_all_process_info():
            mapping[info.host][info.name] = info

        return mapping

    def get_process_info(self, host, name):
        process_info = self._process_info_by_host_name()[host][name]
        return HQSupervisorApi._add_host(host, process_info)

    def start_process(self, host, name, wait=True):
        return self.servers[host].start_process(name, wait=wait)

    def stop_process(self, host, name, wait=True):
        return self.servers[host].stop_process(name, wait=wait)

    def restart_process(self, host, name, wait=True):
        return self.servers[host].restart_process(name, wait)


class PillowtopSupervisorApi(HQSupervisorApi):

    def __init__(self):
        super(PillowtopSupervisorApi, self).__init__('pillowtop')

    @memoized
    def get_pillow_process_info(self, pillow_name):
        process_info = [
            info for info in self.get_all_process_info()
            if pillow_name in info.name
        ]
        try:
            return process_info[0]
        except IndexError:
            raise SupervisorException('Process not found for pillow: {}'.format(pillow_name))

    def refresh_process_infos(self):
        self.get_pillow_process_info.reset_cache()
        super(PillowtopSupervisorApi, self).refresh_process_infos()

    def start_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        return self.start_process(info.host, info.name)

    def stop_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        return self.stop_process(info.host, info.name)

    def restart_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        return self.restart_process(info.host, info.name)


def pillow_supervisor_status(pillow_name):
    return all_pillows_supervisor_status([pillow_name])[pillow_name]


def all_pillows_supervisor_status(pillow_names):
    def status(state, message=None):
        return {
            'supervisor_state': state,
            'supervisor_message': message
        }

    try:
        supervisor = PillowtopSupervisorApi()
    except Exception as e:
        return {name: status('(unavailable)', str(e)) for name in pillow_names}

    def get_status(pillow_name):
        try:
            info = supervisor.get_pillow_process_info(pillow_name)
            return status(info.statename)
        except Exception as e:
            return status('UNKNOWN', str(e))

    return {name: get_status(name) for name in pillow_names}

