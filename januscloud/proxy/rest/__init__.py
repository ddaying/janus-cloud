# -*- coding: utf-8 -*-


def includeme(config):
    # look into following modules' includeme function
    # in order to register routes
    config.include(__name__ + '.client')
    config.include(__name__ + '.backend_server_view')
    config.scan()
