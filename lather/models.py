# -*- coding: utf-8 -*-
import logging

from .exceptions import *
from .decorators import *

log = logging.getLogger('lather_client')


class Field(object):
    """
    Suds library de-serialize the attributes, there is no need for
    de-serialization. Suds library also cares about the serialization. So in
    this class we only define the validators
    """

    def __init__(self, name=None, max_length=None, min_length=None,
                 validators=None, default=None):
        self.name = name
        self.min_length = min_length
        self.max_length = max_length
        self._validators = validators if validators else []
        self.default_validators = []
        self.error_messages = {}
        self.default = default

        # Special attr for the unresolved fields
        self._blank = False

    def __repr__(self):
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        name = getattr(self, 'name', None)
        if name is not None:
            return '<%s: %s>' % (path, name)
        return '<%s>' % path

    @property
    def validators(self):
        return self.default_validators + self._validators

    def check(self, **kwargs):
        errors = []
        return errors

    def contribute_to_class(self, model, name):
        if not self.name:
            self.name = name
        self.model = model

    def run_validators(self, value):
        errors = []
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                errors.extend(e)

        if errors:
            raise ValidationError(errors)

    def clean(self, value):
        self.run_validators(value)
        return value


class QuerySet(object):
    def __init__(self, manager, model):
        self.manager = manager
        self.model = model
        self.queryset = None

    def __len__(self):
        return self.count()

    def __iter__(self):
        if not self.queryset:
            raise Exception('No queryset found')

        return iter(self.queryset)

    def __getattr__(self, item):
        log.debug('[%s] Calling queryset __getattr__: %s' % (log.name.upper(),
                                                             item))
        for codeunit in self.model._meta.codeunit_pages:
            client = self._connect(codeunit)
            services = dict((service.lower(), service) for service in
                            client.get_services())
            if item in services.keys():
                def wrapper(*args, **kwargs):
                    log.debug('[%s] called with %r and %r' % (log.name.upper(),
                                                              args, kwargs))
                    companies = self.model.client.companies
                    for company in companies:
                        # TODO: Create dynamically a new class from Model
                        # with the same name as the codeunit and save the
                        # results
                        new_client = self._connect(codeunit, company)
                        func = getattr(new_client, services[service])
                        return func(*args, **kwargs)

                return wrapper
        raise AttributeError(item)

    def _connect(self, company=None, page=None):
        """
        Central method which makes the connection to the api
        """
        if not page:
            page = self.model._meta.page

        return self.model.client.connect(page, company)

    def _query(self, client, method, **kwargs):
        """
        Central method which executes the api calls
        """
        if not method:
            raise TypeError('Method must be string not None.')
        if kwargs.get('attrs', None):
            return getattr(client, method)(kwargs.get('attrs'))
        return getattr(client, method)(**kwargs)

    def _check_kwargs(self, method, **kwargs):
        params = self.model.client.get_service_params(method,
                                                      self.model._meta.page)
        # Because, elements are suds.sax.text.Text, convert them to str
        params = [str(x[0]) for x in params]
        if params:
            if len(kwargs.keys()) > len(params):
                raise AttributeError('You specify too many arguments.')
            for k in params:
                if k not in kwargs.keys():
                    raise AttributeError('You have to specify the arg: %s' % k)

    @require_client
    def create(self, obj=None, companies=None, **kwargs):
        if obj:
            # Send the create action to the appropriate companies
            for key in obj.get_key_objects():
                # If the key object contains the key attribute then came from
                # the update_or_create() -> update() -> create() because the
                # user added some new companies, so the instance contains
                # some key objects with key
                if key.key:
                    continue
                client = key.client
                if not client:
                    client = self._connect(key.company)

                attrs = dict(attrs=kwargs)
                response = self._query(client, self.model._meta.create,
                                       **attrs)
                obj.populate_attrs(response)
                obj.add_key(key.company, client,
                            getattr(response, self.model._meta.default_id))
        else:
            inst = None
            if not companies:
                companies = self.model.client.companies
            for company in companies:
                client = self._connect(company)
                attrs = dict(attrs=kwargs)
                response = self._query(client, self.model._meta.create,
                                       **attrs)
                if not inst:
                    inst = self.model()
                    inst.populate_attrs(response)
                inst.add_key(company, client,
                             getattr(response, self.model._meta.default_id))

            return inst

    @require_client
    def all(self):
        self.queryset = []
        companies = self.model.client.companies
        for company in companies:
            client = self._connect(company)

            response = iter(self._query(client, self.model._meta.all))

            for result in response:
                log.debug('[%s] From the company %s we got the result: %s'
                          % (log.name.upper(), company, result))
                inst = self.model()
                inst.populate_attrs(result)
                inst.add_key(company, client,
                             getattr(result, self.model._meta.default_id))

                if self.queryset:
                    found = False
                    for obj in self.queryset:
                        if inst == obj:
                            obj_keys = getattr(obj,
                                               self.model._meta.default_id)
                            inst_keys = getattr(inst,
                                                self.model._meta.default_id)
                            obj_keys.extend(inst_keys)
                            found = True

                    if not found:
                        self.queryset.append(inst)
                else:
                    self.queryset.append(inst)

        return self

    @require_client
    def get(self, **kwargs):
        self._check_kwargs(self.model._meta.get, **kwargs)

        self.queryset = []
        companies = self.model.client.companies
        for company in companies:
            client = self._connect(company)
            # When the result is None the suds raise AttributeError, handle
            # this error to return ObjectNotFound
            try:
                # response = getattr(client, self.model._meta.get)(**kwargs)
                response = self._query(client, self.model._meta.get, **kwargs)
            except AttributeError:
                continue

            if isinstance(response, list):
                raise Exception('This function can return only one object but '
                                'the query returned multiple results. '
                                'Use all instead')

            inst = self.model()
            inst.populate_attrs(response)
            inst.add_key(company, client,
                         getattr(response, self.model._meta.default_id))

            if self.queryset:
                found = False
                for obj in self.queryset:
                    # TODO: Test keys (if are the same at all companies ) and
                    # TODO: give Warning about this
                    if inst == obj:
                        obj_keys = getattr(obj, self.model._meta.default_id)
                        inst_keys = getattr(inst, self.model._meta.default_id)
                        obj_keys.extend(inst_keys)
                        found = True

                if not found:
                    self.queryset.append(inst)

            else:
                self.queryset.append(inst)

        if len(self.queryset) > 1:
            return self
        elif len(self.queryset) == 1:
            return self.queryset[0]
        else:
            raise ObjectDoesNotExist('Object not found')

    @require_client
    def update(self, obj=None, companies=None, **kwargs):
        if obj:
            # This if will be true when the previous funciton is the
            # update_or_create
            if self.queryset:
                for inst in self.queryset:
                    # Finally we will have:
                    # add_companies: contains new companies and will create
                    # update_companies: contains existing companies and will update
                    # delete_companies: contains deleted companies and will delete
                    add_companies = []
                    existing_companies = inst.get_companies()
                    delete_companies = []
                    if companies:
                        add_companies = companies[:]
                        update_companies = []
                        for company in existing_companies:
                            if company in add_companies:
                                update_companies.append(company)
                                add_companies.pop(add_companies.index(company))
                            else:
                                delete_companies.append(company)
                    else:
                        update_companies = existing_companies[:]

                    for key in inst.get_key_objects():
                        if key.company in update_companies:
                            kwargs.update(
                                {self.model._meta.default_id: key.key})
                            client = key.client
                            if not client:
                                client = self._connect(key.company)

                            attrs = dict(attrs=kwargs)
                            response = self._query(client,
                                                   self.model._meta.update,
                                                   **attrs)
                            inst.populate_attrs(response)
                            inst.add_key(key.company, client,
                                         getattr(response,
                                                 self.model._meta.default_id))
                        elif key.company in delete_companies:
                            tmp_dict = {self.model._meta.default_id: str(key.key)}
                            self.delete(**tmp_dict)
                            inst.remove_key(key)
                    # Now create the new entries
                    if add_companies:
                        inst.add_companies(add_companies)
                        inst.save()
            else:
                for key in obj.get_key_objects():
                    kwargs.update({self.model._meta.default_id: key.key})
                    client = key.client
                    if not client:
                        client = self._connect(key.company)

                    attrs = dict(attrs=kwargs)
                    response = self._query(client, self.model._meta.update,
                                           **attrs)
                    obj.populate_attrs(response)
                    obj.add_key(key.company, client,
                                getattr(response, self.model._meta.default_id))
        else:
            inst = None
            keys = kwargs.pop(self.model._meta.default_id, None)
            if not keys:
                raise TypeError("You have to provide a keyword: %s"
                                % self.model._meta.default_id)

            if isinstance(keys, list):
                for key in keys:
                    if not isinstance(key, Key):
                        raise TypeError('The list must contain Key objects')

                    client = key.client
                    if not client:
                        client = self._connect(key.company)
                    kwargs.update({self.model._meta.default_id: key.key})
                    response = getattr(client, self.model._meta.update)(kwargs)
                    if not inst:
                        inst = self.model()
                        inst.populate_attrs(response)
                    inst.add_key(key.company, client,
                                 getattr(response,
                                         self.model._meta.default_id))
            else:
                # TODO: Does not work for some reason, maybe needs the company
                if not companies:
                    companies = self.model.client.companies
                for company in companies:
                    client = self._connect(company)
                    kwargs.update({self.model._meta.default_id: keys})
                    response = getattr(client, self.model._meta.update)(kwargs)
                    if not inst:
                        inst = self.model()
                        inst.populate_attrs(response)
                    inst.add_key(company, client,
                                 getattr(response,
                                         self.model._meta.default_id))

            return inst

    @require_client
    def delete(self, obj=None, **kwargs):
        success = True
        if obj:
            # Send the delete action to the appropriate companies
            for key in obj.get_key_objects():
                client = key.client
                if not client:
                    client = self._connect(key.company)
                tmp_dict = {self.model._meta.default_id: key.key}
                if not self._query(client, self.model._meta.delete,
                                   **tmp_dict):
                    success = False
        else:
            # Send the delete action to all the companies
            # TODO: Maybe run first a get or filter to get the object
            # TODO: because the same Key may not be unique
            keys = kwargs.get(self.model._meta.default_id, None)
            if self.queryset and not keys:
                tmp_list = self.queryset[:]
                for result in self.queryset:
                    success = True
                    for key in getattr(result, self.model._meta.default_id):
                        if not isinstance(key, Key):
                            raise TypeError(
                                'The list must contain Key objects')
                        client = key.client
                        if not client:
                            client = self._connect(key.company)
                        tmp_dict = {self.model._meta.default_id: key.key}
                        if not self._query(client, self.model._meta.delete,
                                           **tmp_dict):
                            success = False
                    if success:
                        tmp_list.pop(tmp_list.index(result))
                # Assign the undeleted objects
                self.queryset = tmp_list[:]
            else:
                if not keys:
                    raise Exception('You have to provide a keyword: %s'
                                    % self.model._meta.default_id)

                if isinstance(keys, list):
                    for key in keys:
                        if not isinstance(key, Key):
                            raise TypeError(
                                'The list must contain Key objects')
                        client = key.client
                        if not client:
                            client = self._connect(key.company)
                        tmp_dict = {self.model._meta.default_id: key.key}
                        if not self._query(client, self.model._meta.delete,
                                           **tmp_dict):
                            success = False

                else:
                    companies = self.model.client.companies
                    for company in companies:
                        client = self._connect(company)
                        # TODO: catch more accurate the error: Webfault
                        # because whenever tries to delete somthing which
                        # doesn't exist raise this error
                        try:
                            if not self._query(client, self.model._meta.delete,
                                           **kwargs):
                                success = False
                        except:
                            continue
        return success

    @require_client
    @require_default
    def get_or_create(self, companies=None, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
        # Sometimes, the returning object doesn't contain all the attributes
        # from the defaults so if you specify a new value to an atttibute
        # contained in the defaults but not in the returned object, it will not
        # saved, so we are going to add this attributes to the declared_fields
        if not self.model._meta.declared_fields:
            self.model._meta.add_declared_fields_from_names(defaults.keys())

        try:
            inst = self.get(**kwargs)
            created = False
        except ObjectDoesNotExist:
            # Update the defaults with the kwargs which contains the query
            # fields
            duplicate_keys = [key for key in defaults.keys()
                              if key in kwargs.keys()]
            if duplicate_keys:
                raise AttributeError('Duplicate keys at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keys))

            if self.model._meta.declared_fields:
                non_declared_fields = [key for key in defaults.keys() if
                                       key not in self.model._meta.get_declared_field_names()]
                if non_declared_fields:
                    raise AttributeError('Some of the keys are not specified '
                                         'at the fields: %s'
                                         % ', '.join(non_declared_fields))
            kwargs.update(defaults)
            inst = self.create(companies=companies, **kwargs)
            created = True
        return inst, created

    @require_client
    @require_default
    def update_or_create(self, companies=None, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
        # Same as above
        if not self.model._meta.declared_fields:
            self.model._meta.add_declared_fields_from_names(defaults.keys())

        try:
            inst = self.get(**kwargs)
            self.update(inst, companies, **defaults)
            created = False
        except ObjectDoesNotExist:
            # Update the defaults with the kwargs which contains the query
            # fields
            duplicate_keys = [key for key in defaults.keys()
                              if key in kwargs.keys()]
            if duplicate_keys:
                raise AttributeError('Duplicate keys at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keys))

            if self.model._meta.declared_fields:
                non_declared_fields = [key for key in defaults.keys() if
                                       key not in self.model._meta.get_declared_field_names()]
                if non_declared_fields:
                    raise AttributeError('Some of the keys are not specified '
                                         'at the fields: %s'
                                         % ', '.join(non_declared_fields))
            kwargs.update(defaults)
            inst = self.create(companies=companies, **kwargs)
            created = True
        return inst, created

    @require_client
    def filter(self, **kwargs):
        self.queryset = []
        companies = self.model.client.companies
        for company in companies:
            client = self._connect(company)
            params = client.get_service_params(self.model._meta.filter)

            filters = []
            for k in kwargs.keys():
                filter = client.factory(params[0][1].type[0])
                setattr(filter, 'Field', k)
                setattr(filter, 'Criteria', kwargs.get(k))
                filters.append(filter)

                # TODO: Try pipe filters
                try:
                    response = iter(
                        getattr(client, self.model._meta.filter)(filters)[0])
                except IndexError:
                    continue

                for result in response:
                    log.debug('[%s] From the company %s we got the result: %s'
                              % (log.name.upper(), company, result))
                    inst = self.model()
                    inst.populate_attrs(result)
                    inst.add_key(company, client,
                                 getattr(result, self.model._meta.default_id))

                    if self.queryset:
                        found = False
                        for obj in self.queryset:
                            if inst == obj:
                                obj_keys = getattr(obj,
                                                   self.model._meta.default_id)
                                inst_keys = getattr(inst,
                                                    self.model._meta.default_id)
                                obj_keys.extend(inst_keys)
                                found = True

                        if not found:
                            self.queryset.append(inst)
                    else:
                        self.queryset.append(inst)

        return self

    def count(self):
        """
        Return the number of the results if the queryset exists
        """
        if not self.queryset:
            raise Exception('No queryset found')

        return len(list(self.queryset))


class Manager(object):
    def __init__(self, model):
        self.model = model

    def __getattr__(self, item):
        log.debug('[%s] Calling manager __getattr__: %s' % (log.name.upper(),
                                                            item))
        if hasattr(QuerySet, item):
            def wrapper(*args, **kwargs):
                log.debug('[%s] called with %r and %r' % (log.name.upper(),
                                                          args, kwargs))
                queryset = QuerySet(self, self.model)
                func = getattr(queryset, item)
                return func(*args, **kwargs)

            return wrapper
        raise AttributeError(item)


class Key(object):
    def __init__(self, company, key=None, client=None):
        self.company = company
        self.key = key
        self.client = client

    def __repr__(self):
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        key = getattr(self, 'key', None)
        if key is not None:
            return '<%s: %s>' % (path, key)
        return '<%s>' % path


class Options(object):
    def __init__(self, meta=None):
        self.meta = meta
        self.model = None
        self.create = 'Create'
        self.get = 'Read'
        self.all = None
        self.update = 'Update'
        self.delete = 'Delete'
        self.filter = 'ReadMultiple'
        self.manager = Manager
        self.fields = None
        self.default_id = 'Key'
        self.declared_fields = []
        self.discovered_fields = []
        self.codeunit_pages = []
        self.readonly_fields = []
        self._page = None

    def add_default_codeunit_page(self):
        if not self.codeunit_pages:
            default_codeunit_page = 'Codeunit/%s' % self.page.split('/')[-1]
            self.codeunit_pages.append(default_codeunit_page)

    @property
    def page(self):
        if self._page:
            return self._page
        elif self.model:
            return 'Page/%s' % self.model.__name__
        else:
            raise Exception('Model is not specified')

    @page.setter
    def page(self, value):
        self._page = value

    def get_field_names(self):
        """
        Return a list of names of all the fields (declared and discovered)
        """
        return list(set([f.name for f in self.declared_fields] +
                        [f.name for f in self.discovered_fields]))

    def get_declared_field_names(self):
        """
        Return a list of names of the declared fields
        """
        return [f.name for f in self.declared_fields]

    def get_discovered_field_names(self):
        """
        Return a list of names of the declared fields
        """
        return [f.name for f in self.discovered_fields]

    def add_declared_fields_from_names(self, fields):
        """
        Create field objects from the field names
        """
        if not isinstance(fields, list):
            raise TypeError('This function expects list of field names.')

        if len(fields) != len(set(fields)):
            raise TypeError('The fields attribute contains duplicate field '
                            'names.')

        for f in set(fields):
            self.add_declared_field_from_name(f)

    def add_declared_field_from_name(self, field):
        """
        Create declared field object from the field name
        """
        if field not in self.get_declared_field_names():
            f = Field(name=field)
            self.declared_fields.append(f)

    def add_discovered_field_from_name(self, field):
        """
        Create discovered field object from the field name
        """
        if field not in self.get_discovered_field_names() \
                and field not in self.get_declared_field_names():
            f = Field(name=field)
            self.discovered_fields.append(f)


class BaseModel(type):
    def __new__(cls, name, bases, nmspc):
        super_new = super(BaseModel, cls).__new__

        parents = [b for b in bases if isinstance(b, BaseModel)]

        module = nmspc.pop('__module__')
        new_cls = super_new(cls, name, bases, {'__module__': module})

        # Get class Meta options
        meta = nmspc.pop('Meta', None)
        new_cls._meta = Options(meta)

        for opt in dir(meta):
            if opt.find('__') == -1:
                setattr(new_cls._meta, opt, getattr(meta, opt))

        # Do the appropriate setup for any model parents.
        for base in parents:
            if not hasattr(base, '_meta'):
                # Things without _meta aren't functional models, so they're
                # uninteresting parents.
                continue

            parent_fields = base._meta.declared_fields
            # Exam if the parent define new fields
            for field in parent_fields:
                if field.name in [x.name for x in
                                  new_cls._meta.declared_fields]:
                    raise FieldException('The field %s arleady exist in '
                                         'another parent.' % field.name)
                else:
                    new_cls._meta.declared_fields.append(field)

        # TODO: Maybe not needed
        # Register the Key attribute which will contain all the diferent keys
        setattr(new_cls, new_cls._meta.default_id, None)

        # Register the rest of the fields
        fields_errors = []
        for obj_name, obj in nmspc.items():
            if not isinstance(obj, Field):
                setattr(new_cls, obj_name, obj)
            else:
                if new_cls._meta.fields:
                    raise FieldException("You can't define custom fields when "
                                         "you have set the fields meta "
                                         "attribute.")
                if obj_name == new_cls._meta.default_id:
                    raise FieldException('The fields contains an existing '
                                         'field: %s' % new_cls._meta.default_id)
                if obj_name in [x.name for x in new_cls._meta.declared_fields]:
                    raise FieldException('The field %s arleady exist in '
                                         % field.name)
                # Contribute to fields the model class and the name of the
                # variable (name of the field)
                obj.contribute_to_class(new_cls, obj_name)
                fields_errors.extend(obj.check())
                new_cls._meta.declared_fields.append(obj)

        if fields_errors:
            from termcolor import colored
            for field_error in fields_errors:
                print '%s: %s' % (colored(field_error[0], 'red'),
                                  field_error[1])
            raise FieldException('Field errors.')

        # Assign the model class to the Options instance and add the default
        # codeunit page if is empty
        new_cls._meta.model = new_cls
        new_cls._meta.add_default_codeunit_page()

        return new_cls


class Model(object):
    __metaclass__ = BaseModel
    client = None
    objects = None

    def __init__(self, *args, **kwargs):
        # Initialize the default_id to an empty list
        setattr(self, self._meta.default_id, [])

        # Initialize attributes to the field default value
        for field in self._meta.declared_fields:
            setattr(self, field.name, field.default)

        if args:
            # If the model has no custom fields you can't initialize an
            # instance providing only args, otherwise create attributes from
            # the declared_fields_names
            if not self._meta.declared_fields:
                raise TypeError(
                    'You cannot pass args without specifing custom fields.')
            else:
                if len(args) > len(self._meta.get_declared_field_names()):
                    raise TypeError('Too many arguments. You can set '
                                    'only %s'
                                    % len(self._meta.declared_fields))
                for count, arg in enumerate(args):
                    setattr(self, self._meta.declared_fields[count].name, arg)

        if kwargs:
            if not self._meta.declared_fields:
                for k in kwargs:
                    # Because the declared_fields is empty, add field
                    # from the kwargs because it will be needed at the
                    # save
                    self._meta.add_declared_field_from_name(k)
                    setattr(self, k, kwargs.get(k))
            else:
                for k in kwargs:
                    if k not in self._meta.get_declared_field_names():
                        raise TypeError(
                            "'%s' is an invalid keyword argument" % k)
                    setattr(self, k, kwargs.get(k))

    def __getattr__(self, item):
        """
        Handle calls to the discovered fields (a previous object add some
        fields and the current one doesn't contain these field causing the
        __eq__ to fail because of AttributeError)
        """
        log.debug('[%s] Calling model __getattr__: %s' % (log.name.upper(),
                                                          item))
        if item in self._meta.get_discovered_field_names():
            return None
        else:
            AttributeError(item)

    def __eq__(self, other):
        """
        Exam if two objects are equal
        """
        for field in self._meta.get_field_names():
            try:
                if getattr(self, field) != getattr(other, field):
                    return False
            except AttributeError:
                return False
        return True

    def _add_discoved_field(self, attr):
        """
        Add undeclared fields from the reponse to the discovered_fields
        """
        if attr != self._meta.default_id:
            self._meta.add_discovered_field_from_name(attr)

    def populate_attrs(self, response):
        # Remove key from the keylist because it's handled from the add_key
        try:
            response.__keylist__.pop(
                response.__keylist__.index(self._meta.default_id))
        except ValueError:
            pass
        # Suds keylist sometimes does not contain all the fields, because
        # they do not contain any info. If these fields are specified at
        # the model definition, add them with the default value.
        # unresolved_fields: contains the field names which are specified but
        # they don't contained to the response
        unresolved_fields = self._meta.get_declared_field_names()
        for attr in response.__keylist__:
            try:
                unresolved_fields.pop(unresolved_fields.index(attr))
            except ValueError:
                pass
            setattr(self, attr, getattr(response, attr))
            # Fill the rest fields to the discovered fields option
            # Maybe will need them
            self._add_discoved_field(attr)

        if unresolved_fields:
            for attr in unresolved_fields:
                for f in self._meta.declared_fields:
                    if f.name == attr:
                        f._blank = True
                        break

    def add_companies(self, companies):
        """
        Add companies to the object
        """
        for company in companies:
            keys = getattr(self, self._meta.default_id)
            keys.append(Key(company))

    def remove_key(self, key):
        """
        Removes a Key instance from the default_id attribute
        """
        index = None
        for count, _key in enumerate(getattr(self, self._meta.default_id)):
            if _key.key == key:
                index = count
                break

        if index:
            getattr(self, self._meta.default_id).pop(index)

    def add_key(self, company, client, key):
        """
        Adds a Key instance at the instance default_id (for example on get)
        or update a company's information (for example at the save)
        """
        for _key in getattr(self, self._meta.default_id):
            if _key.company == company:
                _key.client, _key.key = client, key
                return

        keys = getattr(self, self._meta.default_id)
        keys.append(Key(company, key, client))

    def get_keys(self):
        """
        Return all the keys for this object
        """
        keys = []
        for key in getattr(self, self._meta.default_id):
            if key.key:
                keys.append(key.key)

        return keys

    def get_companies(self):
        """
        Return all the companies for this object
        """
        companies = []
        for key in getattr(self, self._meta.default_id):
            if key.company:
                companies.append(key.company)

        return companies

    def get_key_objects(self):
        """
        Return the the Key objects
        """
        return getattr(self, self._meta.default_id)

    def clean(self, exclude=None):
        """
        Cleans all fields and raises a ValidationError containing a dict
        of all validation errors if any occur.
        """
        if exclude is None:
            exclude = []

        errors = {}
        for f in self._meta.declared_fields:
            if f.name in exclude:
                continue

            # If the field is unresolved or specified by the model, pass the
            # validation because it does not contain any value
            if f._blank:
                continue

            raw_value = getattr(self, f.name)
            try:
                setattr(self, f.name, f.clean(raw_value))
            except ValidationError as e:
                errors[f.name] = e

        if errors:
            raise ValidationError(errors)

    @require_client
    def save(self):
        """
        Saves or updates the object
        """
        self.clean()
        # Create dict with all the fields (declared and discovered)
        # TODO: add reaonly fields to ignore at this point because some of them
        # maybe cannot handle it from the backend
        tmp_dict = dict((field, getattr(self, field)) for field in
                        self._meta.get_field_names() if
                        field not in self._meta.readonly_fields)

        # If there wans't any change at the companies just update, otherwise
        # run create which handles these new companies
        if len(self.get_keys()) == len(self.get_companies()):
            self.objects.update(obj=self, **tmp_dict)
        else:
            self.objects.create(obj=self, **tmp_dict)

    @require_client
    def delete(self):
        """
        Deletes the object
        """
        return self.objects.delete(obj=self)
