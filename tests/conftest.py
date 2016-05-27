# -*- coding: utf-8 -*-
import pytest
import os

from suds.transport.http import HttpTransport
from suds.reader import DocumentReader
from suds.sax.parser import Parser


class Reply:

    def __init__(self, response):
        self.message = response


def download(reader, url):
    company = None
    info =  url.split('/')
    filename = 'mocks/%s.xml' % info[-1].lower()

    # If the url contains the company name, take it and append it to response
    if len(info) == 3:
        company = info[0]
    with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
        response = f.read()
        sax = Parser()
        result = sax.parse(string=response)
        if company:
            element = result.children[0].children[-1].children[0].children[0]
            location = element.get('location')
            element.set('location', '%s/%s' %(company, location))
        return result


def send(transport, request):
    company = None
    method = request.headers['SOAPAction'].split(':')[2].strip('"').lower()
    info = request.url.split('/')
    if len(info) == 3:
        company = info[0]

    if company and company == 'Company1' and method == 'read_diff':
        filename = 'mocks/read_diff_company1.xml'
    elif company and company == 'Company2' and method == 'read_diff':
        filename = 'mocks/read_diff_company2.xml'
    elif company and company == 'Company1' and method == 'delete_diff':
        filename = 'mocks/delete_diff_company1.xml'
    else:
        filename = 'mocks/%s.xml' % method
    with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
        response = f.read()
        reply = Reply(response)
        return reply


@pytest.fixture(autouse=True)
def mock(monkeypatch):
    monkeypatch.setattr(DocumentReader, 'download', download)
    monkeypatch.setattr(HttpTransport, 'send', send)