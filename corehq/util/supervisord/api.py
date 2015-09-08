from collections import namedtuple
import os
import xmlrpclib
from amqplib.client_0_8.method_framing import defaultdict
from ansible.inventory import InventoryParser
from django.conf import settings
from django.utils.functional import memoize
from jsonobject.api import JsonObject
from jsonobject.properties import StringProperty, IntegerProperty
from dimagi.utils.decorators.memoized import memoized

SERVER_STATE_RUNNING = 1


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


def get_inventory():
    filename = os.path.join('fab', 'inventory', settings.SERVER_ENVIRONMENT)
    return {
        name: [host.name for host in group.get_hosts()]
        for name, group in InventoryParser(filename).groups.items()
    }


def get_inventory_group(group):
    return get_inventory().get(group, [])


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
        print self._url
        self._server = xmlrpclib.Server(self._url)
        self.check_state()

    def check_state(self):
        state = self._server.supervisor.getState()
        if state['statecode'] != SERVER_STATE_RUNNING:
            raise SupervisorException('Supervisord is not running: {}'.format(state['statename']))

    def get_all_process_info(self):
        return [ProcessInfo.wrap(info) for info in self._server.supervisor.getAllProcessInfo()]

    def get_process_info(self, name):
        return ProcessInfo.wrap(self._server.supervisor.getProcessInfo(name))

    def start_process(self, name, wait=True):
        return self._server.supervisor.startProcess(name, wait=wait)

    def stop_process(self, name, wait=True):
        return self._server.supervisor.stopProcess(name, wait=wait)

    def restart_process(self, name, wait=True):
        return self.stop_process(name, wait) and self.start_process(name, wait)


class HQSupervisorApi(object):
    def __init__(self, inventory_group):
        self.inventory_group = inventory_group
        self.servers = {
            host: SupervisorApi(host)
            for host in get_inventory_group(inventory_group)
        }

    @staticmethod
    def _add_host(process_info, host):
        process_info.host = host
        return process_info

    @memoized
    def get_all_process_info(self):
        return [
            HQSupervisorApi._add_host(host, process_info)
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
            raise SupervisorException('No pillow process found with name: {}'.format(pillow_name))

    def refresh_process_infos(self):
        self.get_pillow_process_info.reset_cache()
        super(PillowtopSupervisorApi, self).refresh_process_infos()

    def start_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        self.start_process(info.host, info.name)

    def stop_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        self.stop_process(info.host, info.name)

    def restart_pillow(self, pillow_name):
        info = self.get_pillow_process_info(pillow_name)
        self.restart_process(info.host, info.name)
