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

    def __str__(self):
        return '%s.%s' % (self.model.__name__, self.name)

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

    def _connect(self, company):
        return self.model.client.connect(self.model._meta.page, company)

    def _query(self, client, method, **kwargs):
        # TODO: Implement for central handling of requests
        pass

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
    def create(self, obj=None, **kwargs):
        if obj:
            # Send the create action to the appropriate companies
            for key in obj.get_key_objects():
                client = key.client
                if not client:
                    client = self._connect(key.company)

                response = getattr(client, self.model._meta.create)(kwargs)
                obj.populate_attrs(response)
                obj.add_key(key.company, client,
                            getattr(response, self.model._meta.default_id))
        else:
            inst = None
            companies = self.model.client.companies
            for company in companies:
                client = self._connect(company)
                response = getattr(client, self.model._meta.create)(kwargs)
                if not inst:
                    inst = self.model()
                    inst.populate_attrs(response)
                inst.add_key(company, client,
                             getattr(response, self.model._meta.default_id))

            return inst

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
                response = getattr(client, self.model._meta.get)(**kwargs)
            except AttributeError:
                continue
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
    def update(self, obj=None, **kwargs):
        if obj:
            for key in obj.get_key_objects():
                kwargs.update({self.model._meta.default_id: key.key})
                client = key.client
                if not client:
                    client = self._connect(key.company)

                response = getattr(client, self.model._meta.update)(kwargs)
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
                                 getattr(response, self.model._meta.default_id))
            else:
                # TODO: Does not work for some reason, maybe needs the company
                companies = self.model.client.companies
                for company in companies:
                    client = self._connect(company)
                    kwargs.update({self.model._meta.default_id: keys})
                    response = getattr(client, self.model._meta.update)(kwargs)
                    if not inst:
                        inst = self.model()
                        inst.populate_attrs(response)
                    inst.add_key(company, client,
                                 getattr(response, self.model._meta.default_id))

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
                if not getattr(client, self.model._meta.delete)(**tmp_dict):
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
                            raise TypeError('The list must contain Key objects')
                        client = key.client
                        if not client:
                            client = self._connect(key.company)
                        tmp_dict = {self.model._meta.default_id: key.key}
                        if not getattr(client, self.model._meta.delete)(**tmp_dict):
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
                            raise TypeError('The list must contain Key objects')
                        client = key.client
                        if not client:
                            client = self._connect(key.company)
                        tmp_dict = {self.model._meta.default_id: key.key}
                        if not getattr(client, self.model._meta.delete)(**tmp_dict):
                            success = False

                else:
                    companies = self.model.client.companies
                    for company in companies:
                        client = self._connect(company)
                        if not getattr(client, self.model._meta.delete)(**kwargs):
                            success = False
        return success

    @require_client
    @require_default
    def get_or_create(self, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
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
                                       key not in [f.name for f in
                                                   self.model._meta.declared_fields]]
                if non_declared_fields:
                    raise AttributeError('Some of the keys are not specified '
                                         'at the fields: %s'
                                         % ', '.join(non_declared_fields))
            kwargs.update(defaults)
            inst = self.create(**kwargs)
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
                    log.debug('From the company %s we got the result: %s'
                              % (company, result))
                    inst = self.model()
                    inst.populate_attrs(result)
                    inst.add_key(company, client,
                                 getattr(result, self.model._meta.default_id))

                    if self.queryset:
                        found = False
                        for obj in self.queryset:
                            if inst == obj:
                                obj_keys = getattr(obj, self.model._meta.default_id)
                                inst_keys = getattr(inst, self.model._meta.default_id)
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
        log.debug("Calling manager __getattr__: %s" % item)
        if hasattr(QuerySet, item):
            def wrapper(*args, **kwargs):
                log.debug('called with %r and %r' % (args, kwargs))
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
        self.update = 'Update'
        self.delete = 'Delete'
        self.filter = 'ReadMultiple'
        self.manager = Manager
        self.fields = None
        self.default_id = 'Key'
        self.declared_fields = []
        # Relative codeunits for this page
        # TODO: Needs work
        self.codeunits = []
        self.discovered_fields = set()
        self._page = None

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

        # Assign the model class to the Options instance
        new_cls._meta.model = new_cls

        return new_cls


class Model(object):
    __metaclass__ = BaseModel
    client = None
    objects = None

    def __init__(self, *args, **kwargs):
        # Initialize the default_id to an empty list
        setattr(self, self._meta.default_id, [])
        # For our purposes, keep the names of the fields
        self.declared_field_names = [f.name for f in
                                     self._meta.declared_fields]

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
                if len(args) > len(self.declared_field_names):
                    raise TypeError('Too many arguments. You can set '
                                         'only %s'
                                         % len(self.declared_field_names))
                for count, arg in enumerate(args):
                    setattr(self, self.declared_field_names[count], arg)

        if kwargs:
            if not self._meta.declared_fields:
                for k in kwargs:
                    setattr(self, k, kwargs.get(k))
                    # Because the declared_field_names is empty, add the field
                    # name from the kwargs because it will be needed at the
                    # save
                    self.declared_field_names.append(k)
            else:
                for k in kwargs:
                    if k not in self.declared_field_names:
                        raise TypeError(
                            "'%s' is an invalid keyword argument" % k)
                    setattr(self, k, kwargs.get(k))

    def __getattr__(self, item):
        """
        Handle calls to the discovered fields (a previous object add some
        fields and the current one doesn't contain these field causing the
        __eq__ to fail because of AttributeError)
        """
        log.debug("Calling model __getattr__: %s" % item)
        if item in self._meta.discovered_fields:
            return None
        else:
            AttributeError(item)

    def __eq__(self, other):
        """
        Exam if two objects are equal
        """
        # TODO: Run the super?
        for field in set(
                self.declared_field_names) | self._meta.discovered_fields:
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
        if attr not in self.declared_field_names and \
                        attr != self._meta.default_id:
            self._meta.discovered_fields.add(attr)

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
        unresolved_fields = self.declared_field_names[:]
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
        tmp_dict = dict((field, getattr(self, field)) for field in
                        self.declared_field_names)

        if self.get_keys():
            self.objects.update(obj=self, **tmp_dict)
        else:
            self.objects.create(obj=self, **tmp_dict)

    @require_client
    def delete(self):
        """
        Deletes the object
        """
        return self.objects.delete(obj=self)
