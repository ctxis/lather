# Lather

Application which provides an `django` like interface to interact with SOAP APIs.

## Requirements
* suds: 0.4
* python-ntlm3

## Setup
* `pip install https://github.com/ctxis/lather/archive/master.zip`

and then add you can use this library like this:

```python
## models.py

from lather import models

class Customer(models.Model):
    pass

customer = Customer.objects.get(user='test')


## settings.py

from lather import client
import models

client = client.LatherClient()
client.register(models.Customer)

customers = Customer.objects.get(key="key")
```

## Support
* Microsoft Dynamics NAV Web Services