# -*- coding: utf-8 -*-


class Response(object):
    """
    Simple class which represent the suds response
    """
    def __init__(self, keylist, dict):
        self.__keylist__ = keylist

        for key in self.__keylist__:
            setattr(self, key, dict[key])

