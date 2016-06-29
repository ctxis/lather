# -*- coding: utf-8 -*-
from lather import exceptions


class Response(object):
    """
    Simple class which represents the suds response
    """
    def __init__(self, keylist, dict):
        self.__keylist__ = keylist

        for key in self.__keylist__:
            setattr(self, key, dict[key])


class MaxLengthValidaiton(object):
    """
    Simple validation class
    """
    def __init__(self, limit_value):
        self.limit_value = limit_value

    def __call__(self, value):
        if len(value) > self.limit_value:
            raise exceptions.ValidationError('Max length reached')

