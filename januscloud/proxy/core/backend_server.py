# -*- coding: utf-8 -*-

import logging
import time
import importlib
import gevent
import random

log = logging.getLogger(__name__)


JANUS_SERVER_STATUS_NORMAL = 0
JANUS_SERVER_STATUS_ABNORMAL = 1


class BackendServer(object):
    """ This backend session represents a session of the backend Janus server """

    def __init__(self, name, url, status, session_timeout=0, location='', isp='', session_num=0, handle_num=0, expire=60):
        self.name = name
        self.url = url
        self.status = status
        self.session_timeout = session_timeout
        self.location = location
        self.isp = isp
        self.session_num = session_num
        self.handle_num = handle_num
        self.expire = expire
        self.utime = time.time()
        self.ctime = time.time()

    def __str__(self):
        return 'Backend Server"{0}"({1})'.format(self.name, self.url)

SERVER_EXPIRE_CHECK_INTERVAL = 60

class BackendServerManager(object):

    def __init__(self, select_mode, static_server_list=[], server_dao=None):

        self._server_dao = server_dao
        self._rr_index = 0
        if select_mode == 'rr':
            self._select_algorithm = self._rr_algo
        elif select_mode == 'rand':
            self._select_algorithm = self._rand_algo
        elif select_mode == 'lb':
            self._select_algorithm = self._rand_algo
        elif ':' in select_mode:
            module_name, sep, method_name = select_mode.partition(':')
            module = importlib.import_module(module_name)
            self._select_algorithm = getattr(module, method_name)

        for server in static_server_list:

            self.update_server(expire=0, **server) # expired == 0 means static server without auto expired

        self._check_expired_greenlet = gevent.spawn(self._check_expired_routine)

    def update_server(self, name, url, status, **kwargs):
        server = self._server_dao.get_by_name(name)
        if server is None:
            server = BackendServer(name, url, status, **kwargs)
            log.info('Backend Server {} ({}) is added into proxy'.format(name, url))

            self._server_dao.add(server)
        else:
            server.url = url
            server.status = status
            for (k, v) in kwargs.items():
                if k in ("session_timeout", "location", "isp", "session_num", "handle_num"):
                    setattr(server, k, v)
            server.utime = time.time()
            self._server_dao.update(server)

    def del_server(self, name):
        server = self._server_dao.get_by_name(name)
        if server:
            log.info('Backend Server {} ({}) is removed from proxy'.format(server.name, server.url))
            self._server_dao.del_by_name(name)

    @staticmethod
    def get_valid_servers(server_dao):
        valid_servers = []
        now = time.time()
        for server in server_dao.get_list():
            if server.status == JANUS_SERVER_STATUS_NORMAL and \
                    (server.expire == 0 or now - server.utime < server.expire):
                valid_servers.append(server)
        return valid_servers


    def _rand_algo(self, server_dao, session_transport):
        server_list = BackendServerManager.get_valid_servers(server_dao)
        if len(server_list) == 0:
            return None
        index = random.randint(0, len(server_list) - 1)
        return server_list[index]

    def _rr_algo(self, server_dao, session_transport):
        server_list = BackendServerManager.get_valid_servers(server_dao)
        if len(server_list) == 0:
            return None
        index = self._rr_index % len(server_list)
        self._rr_index += 1
        return server_list[index]

    def _lb_algo(self, server_dao, session_transport):
        server_list = BackendServerManager.get_valid_servers(server_dao)
        target = None
        for server in server_list:
            if target is None or server.handle_num < target.handle_num:
                target = server

        target.handle_num += 1
        server_dao.update(target)

        return target

    def choose_server(self, transport):
        return self._select_algorithm(self._server_dao, transport)


    def _check_expired_routine(self):
        while True:
            gevent.sleep(SERVER_EXPIRE_CHECK_INTERVAL)
            now = time.time()
            for server in self._server_dao.get_list():
                if server.expire and now - server.utime >= server.expire:
                    log.info('Backend Server {} ({}) expires'.format(server.name, server.url))
                    self._server_dao.del_by_name(server.name)


if __name__ == '__main__':
    pass





