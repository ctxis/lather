# -*- coding: utf-8 -*-
import logging
import urlparse
import urllib

from suds.client import Client
from suds.transport.http import HttpAuthenticated

from .enums import AuthEnums
from .https import NTLMSSPAuthenticated
from .decorators import *

log = logging.getLogger('lather_client')


class WrapperSudsClient(object):
    def __init__(self, endpoint, **kwargs):
        """
        Creates a suds client
        """
        self.client = Client(endpoint, **kwargs)

    def __getattr__(self, item):
        """
        Handle suds service calls
        """
        log.debug('Calling wrapper __getattr__: %s' % item)
        if hasattr(self.client.service, item):
            def wrapper(*args, **kwargs):
                log.debug('called with %r and %r' % (args, kwargs))
                func = getattr(self.client.service, item)
                return func(*args, **kwargs)

            return wrapper
        raise AttributeError(item)

    @require_client
    def factory(self, name):
        """
        Returns the structure of the suds model
        """
        log.debug('Create factory for %s', name)
        return self.client.factory.create(name)

    @require_client
    def get_services(self):
        """
        Get all the services from the soap service url
        """
        return [method for method in
                self.client.wsdl.services[0].ports[0].methods]

    @require_client
    def get_service_params(self, service):
        """
        Get params of the service
        :return: list of tuples, [(name, element),...]
        """
        params = []
        try:
            method = self.client.wsdl.services[0].ports[0].methods[service]
            params = method.binding.input.param_defs(method)
        except KeyError:
            pass

        return params


class LatherClient(object):
    def __init__(self, base, username=None, password=None, auth=AuthEnums.NTLM,
                 proxy=None, cache=True, main='SystemService'):
        self.base = base
        self.username = username
        self.password = password
        self.auth = auth
        self.proxy = proxy
        self.main = main
        self.cache = cache
        self.models = []
        self.companies = []
        self.update_companies()

    def _create_ntlm_auth(self):
        """
        Create the NTLM auth
        """
        ntlm = NTLMSSPAuthenticated(username=self.username,
                                    password=self.password)
        return ntlm

    def _create_basic_auth(self):
        """
        Create the Basic auth
        """
        basic = HttpAuthenticated(username=self.username,
                                 password=self.password)
        return basic

    def _make_options(self):
        """
        Creates the options
        """
        options = dict()
        if self.auth == AuthEnums.NTLM and self.username and self.password:
            options.update(transport=self._create_ntlm_auth())

        if self.auth == AuthEnums.BASIC and self.username and self.password:
            options.update(transport=self._create_basic_auth())

        if self.proxy:
            options.update(proxy=self.proxy)

        if not self.cache:
            options.update(cache=None)

        return options

    def _make_endpoint(self, page, company, direct):
        """
        Creates the endpoint
        """
        if company:
            url = '%s/%s' %(urllib.quote(company), page)
        elif not company and self.companies and not direct:
            url = '%s/%s' %(urllib.quote(self.companies[0]), page)
        else:
            url = page

        return urlparse.urljoin(self.base, url)

    def connect(self, page, company=None, direct=False):
        """
        Creates the connection to the endpoint
        """
        endpoint = self._make_endpoint(page, company, direct)
        options = self._make_options()

        return WrapperSudsClient(endpoint, **options)

    def update_companies(self):
        """
        Make an initial request to the system service endpoint to get all
        the companies
        """
        client = self.connect(self.main)
        self.companies = client.Companies()

    def register(self, model):
        """
        Register model to this client and pass the client to the model
        """
        self.models.append(model)
        model.client = self
        model.objects = model._meta.manager(model)

    #TODO: Duplicate, find a way to remove it
    def get_service_params(self, service, page):
        """
        Get params of the service
        :return: list of tuples, [(name, element),...]
        """
        params = []
        client = self.connect(page, direct=True)
        try:
            method = client.client.wsdl.services[0].ports[0].methods[service]
            params = method.binding.input.param_defs(method)
        except KeyError:
            pass

        return params
