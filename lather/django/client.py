# -*- coding: utf-8 -*-
from django.conf import settings
from lather.client import LatherClient

base_url = getattr(settings, 'LATHER_BASE_URL', None)
username = getattr(settings, 'LATHER_USERNAME', None)
password = getattr(settings, 'LATHER_PASSWORD', None)

lather_client = LatherClient(base_url, username, password)