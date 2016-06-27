# -*- coding: utf-8 -*-
import logging
import urlparse
import urllib

from suds.client import Client
from suds.transport.https import HttpAuthenticated
from suds.plugin import DocumentPlugin
from suds.transport import TransportError

from .enums import AuthEnums, ServiceEnums
from .https import NTLMSSPAuthenticated
from .decorators import *
from .exceptions import *

log = logging.getLogger('lather_client')


class WrapperSudsClient(object):
    def __init__(self, endpoint, **kwargs):
        """
        Creates a suds client
        """
        log.debug('[%s] Calling wrapper __init__: %s' % (log.name.upper(),
                                                         endpoint))
        self.client = None
        try:
            self.client = Client(endpoint, **kwargs)
        except ValueError, e:
            log.error('[%] Failed to make the connection to %s due to '
                      'this error: %s' % (log.name.upper(), endpoint, e))
            raise InvalidBaseUrlException('%s, %s' % (e, 'Maybe the base url '
                                                         'is invalid.'))
        except TransportError, e:
            log.error('[%s] Failed to make the connection to %s due to '
                      'this error: %s' % (log.name.upper(), endpoint, e))
            raise ConnectionError('Connection error: %s' % e)

    def __getattr__(self, item):
        """
        Handle suds service calls
        """
        log.debug('[%s] Calling wrapper __getattr__: %s' % (log.name.upper(),
                                                            item))
        if hasattr(self.client.service, item):
            def wrapper(*args, **kwargs):
                log.debug('[%s] called with %r and %r' % (log.name.upper(),
                                                          args, kwargs))
                func = getattr(self.client.service, item)
                return func(*args, **kwargs)

            return wrapper
        raise AttributeError(item)

    @require_client
    def factory(self, name):
        """
        Returns the structure of the suds model
        """
        log.debug('[%s] Create factory for %s' %(log.name.upper(), name))
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
                 proxy=None, service=ServiceEnums.NAV, main='SystemService',
                 **kwargs):
        self.base = base
        self.username = username
        self.password = password
        self.auth = auth
        self.proxy = proxy
        self.main = main
        self.models = []
        self.options = kwargs
        self.service = service
        self.invalid_companies = kwargs.pop('invalid_companies', [])
        # Initialize companies with a list containing a None object. This is
        # usefull because we dont have to rewrite the QuerySet class. It will
        # iterate over the companies and essentially will make an endpoint
        # without company. Usefull for the Generic services
        self.companies = [None]
        if self.service == ServiceEnums.NAV:
            self.companies = []
            try:
                self.update_companies()
            except:
                pass

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

        # Set the other options
        options.update(**self.options)

        return options

    def _make_endpoint(self, page, company):
        """
        Creates the endpoint
        """
        if company:
            url = '%s/%s' % (urllib.quote(company), page)
        elif self.companies and self.companies[0]:
            url = '%s/%s' % (urllib.quote(self.companies[0]), page)
        else:
            url = page

        return urlparse.urljoin(self.base, url)

    def connect(self, page, company=None):
        """
        Creates the connection to the endpoint
        """
        endpoint = self._make_endpoint(page, company)
        options = self._make_options()

        return WrapperSudsClient(endpoint, **options)

    def update_companies(self):
        """
        Make an initial request to the system service endpoint to get all
        the companies
        """
        if self.service != ServiceEnums.NAV:
            raise Exception('You can only call this function only if the '
                            'system is NAV')
        client = self.connect(self.main)
        self.companies = list(set(client.Companies()) - set(self.invalid_companies))

    def register(self, model):
        """
        Register model to this client and pass the client to the model
        """
        self.models.append(model)
        model.client = self
        model.objects = model._meta.manager(model)

    # TODO: Duplicate, find a way to remove it
    def get_service_params(self, service, page):
        """
        Get params of the service
        :return: list of tuples, [(name, element),...]
        """
        params = []
        client = self.connect(page)
        try:
            method = client.client.wsdl.services[0].ports[0].methods[service]
            params = method.binding.input.param_defs(method)
        except KeyError:
            pass

        return params


class AddService(DocumentPlugin):
    """
    Plugin to manipulate the response of an exchange server
    """

    def loaded(self, ctx):
        """Add missing service."""
        urlprefix = urlparse.urlparse(ctx.url)
        service_url = urlparse.urlunparse(
            urlprefix[:2] + ('/EWS/Exchange.asmx', '', '', ''))
        servicexml = u'''  <wsdl:service name="ExchangeServices">
    <wsdl:port name="ExchangeServicePort" binding="tns:ExchangeServiceBinding">
      <soap:address location="%s"/>
    </wsdl:port>
  </wsdl:service>
</wsdl:definitions>''' % service_url
        ctx.document = ctx.document.replace('</wsdl:definitions>',
                                            servicexml.encode('utf-8'))
        return ctx
