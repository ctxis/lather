# -*- coding: utf-8 -*-
import pytest

from suds.client import Client
from suds.transport.http import HttpAuthenticated

from lather import client, models, https, enums
from .models import *


@pytest.mark.usefixtures("mock")
class TestLatherClient:

    @pytest.fixture
    def latherclient(self):
        return client.LatherClient('test', cache=None)

    def test_make_options_ntlm(self):
        latherclient = client.LatherClient('test', 'test', 'test')
        options = latherclient._make_options()
        assert options['transport']
        assert isinstance(options['transport'], https.NTLMSSPAuthenticated)

    def test_make_options_basic(self):
        latherclient = client.LatherClient('test', 'test', 'test',
                                           enums.AuthEnums.BASIC)
        options = latherclient._make_options()
        assert options['transport']
        assert isinstance(options['transport'], HttpAuthenticated)

    def test_make_options_proxy(self):
        proxy = dict(
            http="http://test.local:3128",
            https="https://test.local:3128"
        )
        latherclient = client.LatherClient('test', proxy=proxy)
        options = latherclient._make_options()
        assert options['proxy'] == proxy

    def test_init(self, latherclient):
        companies = ['Company1', 'Company2', 'Company3', 'Company4']
        assert latherclient.companies == companies

    def test_connect(self, latherclient):
        wrappersudsclient = latherclient.connect('Customer')
        assert isinstance(wrappersudsclient, client.WrapperSudsClient)

    def test_register(self, latherclient):
        latherclient.register(TestModel1)
        assert latherclient.models == [TestModel1]
        assert TestModel1.client == latherclient
        assert isinstance(TestModel1.objects, models.Manager)

    def test_get_service_params(self, latherclient):
        params = latherclient.get_service_params('Read', 'Customer')
        assert len(params) == 1
        assert str(params[0][0]) == 'No'


@pytest.mark.usefixtures("mock")
class TestWrapperSudsClient:

    @pytest.fixture
    def wrappersudsclient(self):
        return client.WrapperSudsClient('Customer')

    def test_init(self, wrappersudsclient):
        assert isinstance(wrappersudsclient.client, Client)

    def test_getattr_1(self, wrappersudsclient):
        response = wrappersudsclient.Read(No='Test')
        assert response.Key == 'Key'

    def test_getattr_1(self, wrappersudsclient):
        with pytest.raises(AttributeError):
            response = wrappersudsclient.Test()

    def test_get_services(self, wrappersudsclient):
        services = [
            'Delete_Diff', 'Read_Diff', 'ReadMultiple', 'CreateMultiple',
            'Read', 'GetRecIdFromKey', 'Create', 'ReadByRecId', 'Update',
            'UpdateMultiple', 'IsUpdated', 'Delete_Fail', 'Read_NotFound',
            'Delete']
        assert wrappersudsclient.get_services() == services

    def test_get_service_params(self, wrappersudsclient):
        params = wrappersudsclient.get_service_params('Read')
        assert len(params) == 1
        assert str(params[0][0]) == 'No'







