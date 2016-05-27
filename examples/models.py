# -*- coding: utf-8 -*-
import logging
import sys
sys.path.append('../lather')

from lather import models, client, enums

import logging
logging.basicConfig()
logging.getLogger('lather_client').setLevel(logging.DEBUG)


class Customer(models.Model):

    class Meta:
        fields = 'all'
        get = 'Read'
        delete = 'Delete'

# Define the base url, the username and the password
base_url = 'http://server/'
username = None
password = None

# Create basic client
#latherclient = LatherClient(base_url, username, password, enums.AuthEnums.BASIC)

# Create ntlm client
latherclient = client.LatherClient(base_url, username, password, cache=False)

# Register the models with the appropriate client
latherclient.register(Customer)

companies = [
    'Company 1',
    'Company 2',
]


## Some examples

# Clear the database from the Test objects from all the companies
customers = Customer.objects.filter(No='Test*')
if customers.queryset:
    print [customer.Name for customer in customers]
    print customers.count()
    result = customers.delete()

# Will create Test object to all the companies
customer1, created = Customer.objects.get_or_create(No='Test',
                                                   defaults={'Name': 'Test'})
# Will get the Test object from all the companies. It will return one object
customer2 = Customer.objects.get(No='Test')

# Will create Test2 object to all the companies
customer3 = Customer.objects.create(No='Test2', Name='Test2')
# Will get the Test2 object from all the companies. It will return one object
customer4 = Customer.objects.get(No='Test2')

# Will update the Test2 Name
customer5 = Customer.objects.update(Key=customer4.Key, Name='Test for example')

# Will create a new instance
new_customer = Customer(No='Test3', Name='Test3')
new_customer.add_companies(companies)
new_customer.save()
new_customer.Name = 'Test3 for example'
new_customer.save()