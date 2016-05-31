# -*- coding: utf-8 -*-
import logging
import sys
sys.path.append('../lather')

from lather import models, client, enums

import logging
logging.basicConfig()
logging.getLogger('lather_client').setLevel(logging.DEBUG)


class CustomerService(models.Model):

    class Meta:
        default_id = 'id'
        fields = 'all'
        all = 'getAll'
        page = 'CustomerService?wsdl'

# Define the base url
base_url = 'http://server/'

# Create client
latherclient = client.LatherClient(base_url,
                                   service=enums.ServiceEnums.GENERIC,
                                   cache=False)

# Register the models with the appropriate client
latherclient.register(CustomerService)

# Fetch all the objects
customers = CustomerService.objects.all()

