# -*- coding: utf-8 -*-
import logging
import sys
sys.path.append('../lather')

from lather import models, client

logging.basicConfig()
logging.getLogger('lather_client').setLevel(logging.DEBUG)


class GlobalWeather(models.Model):

    class Meta:
        default_id = 'id'
        fields = 'all'
        endpoints = (
            ('getweather', {
                'method': 'GetWeather'
            })
        )
        page = 'globalweather.asmx?wsdl'

# Define the base url
base_url = 'http://server'

# Create client
latherclient = client.LatherClient(base_url, cache=None)

# Register the models with the appropriate client
latherclient.register(GlobalWeather)

# Fetch a specific tempurature
obj = GlobalWeather.objects.getweather(CityName='Berlin-Tegel',
                                       CountryName='Germany')