# -*- coding: utf-8 -*-
from django.conf import settings
from lather.client import LatherClient

options = getattr(settings, 'LATHER_CONFIG', None)
lather_client = LatherClient(**options)
