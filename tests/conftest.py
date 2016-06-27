# -*- coding: utf-8 -*-
import pytest
import os

from jinja2 import Environment, FileSystemLoader

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

    tmp = method
    if method.startswith('read') and method != 'readmultiple':
        tmp = 'read'
    elif method.startswith('delete'):
        tmp = 'delete'

    filename = '%s.xml' % tmp
    loader = FileSystemLoader(os.path.join(os.path.dirname(__file__), 'mocks'))
    env = Environment(loader=loader, trim_blocks=True)
    template = env.get_template(filename)

    if method == 'read':
        response = template.render(result=True)
    elif method == 'read_notfound':
        response = template.render(result=False)
    elif method == 'read_diff':
        if company == 'Company1':
            response = template.render(result=True, key='Key0', no='TEST', name='Test_Diff')
        elif company == 'Company2':
            response = template.render(result=True, key='Key1', no='TEST', name='Test')
        else:
            response = template.render(result=True, key='Key0', no='TEST', name='Test')
    elif method == 'delete_diff':
        if company == 'Company1':
            response = template.render(delete='false')
        else:
            response = template.render(delete='true')
    elif method == 'delete_fail':
        response = template.render(delete='false')
    else:
        response = template.render()

    reply = Reply(response)
    return reply


@pytest.fixture(autouse=True)
def mock(monkeypatch):
    monkeypatch.setattr(DocumentReader, 'download', download)
    monkeypatch.setattr(HttpTransport, 'send', send)