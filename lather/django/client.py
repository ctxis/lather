# -*- coding: utf-8 -*-
from django.conf import settings
from lather.client import NavLatherClient


active = getattr(settings, 'LATHER_ENABLE', None)
options = getattr(settings, 'LATHER_CONFIG', None)

if not options and active is None:
    raise AttributeError('You have to specify the "LATHER_ENABLE" or the '
                         '"LATHER_CONFIG" setting options.')

if options and active is None:
    options.update({'active': True})
    setattr(settings, 'LATHER_ENABLE', True)

if active is not None and not options:
    options = {'base': None, 'active': active}

if active == False:
    options = {'base': None, 'active': active}

lather_client = NavLatherClient(**options)
