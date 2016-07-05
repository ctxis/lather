# -*- coding: utf-8 -*-
import sys
import logging

from .exceptions import ValidationError
from .exceptions import FieldException
from .decorators import require_client
from .managers import Manager
from .managers import NavManager
from .managers import BaseQuerySet, QuerySet, NavQuerySet
from .managers import Instance

log = logging.getLogger('lather_client')


class Field(object):
    """
    Suds library de-serializes the attributes, there is no need for
    de-serialization. Suds library also does the serialization. So in
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


class Options(object):
    def __init__(self, meta=None):
        self.meta = meta
        self.model = None
        self.manager = Manager
        self.fields = None
        self.default_id = 'Key'
        self.declared_fields = []
        self.discovered_fields = []
        self.readonly_fields = []
        self._page = None
        self._default_endpoints = (
            ('create', {
                'method': 'Create'
            }),
            ('get', {
                'method': 'Read'
            }),
            ('all', None),
            ('update', {
                'method': 'Update'
            }),
            ('delete', {
                'method': 'Delete'
            }),
            ('filter', {
                'method': 'ReadMultiple'
            })
        )

    def _set_endpoints(self, endpoints):
        for endpoint in endpoints.keys():
            if endpoints.get(endpoint):
                setattr(self, endpoint, endpoints[endpoint]['method'])

                # Attach a general method to the BaseQuerySet which can handle
                # these calls
                if not hasattr(BaseQuerySet, endpoint):
                    def func(cls, **kwargs):
                        method_name = sys._getframe().f_back.f_code.co_name

                        client = cls._connect()
                        return cls._query(client,
                                          getattr(self, method_name),
                                          **kwargs)

                    setattr(BaseQuerySet, endpoint, func)

    #TODO: Deprecated
    def add_default_codeunit_page(self):
        if not self.codeunit_pages:
            default_codeunit_page = 'Codeunit/%s' % self.page.split('/')[-1]
            self.codeunit_pages.append(default_codeunit_page)

    @property
    def endpoints(self):
        return self._default_endpoints

    @endpoints.setter
    def endpoints(self, value):
        new_endpoints = dict(value)
        default_endpoints = dict(self._default_endpoints)
        for k in new_endpoints.keys():
            default_endpoints.update({k:new_endpoints.get(k)})
        self._default_endpoints = default_endpoints

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


class NavOptions(Options):
    def __init__(self, meta=None):
        super(NavOptions, self).__init__(meta)
        self.manager = NavManager


class BaseModel(type):
    def __new__(cls, name, bases, nmspc):
        super_new = super(BaseModel, cls).__new__

        parents = [b for b in bases if isinstance(b, BaseModel)]

        module = nmspc.pop('__module__')
        new_cls = super_new(cls, name, bases, {'__module__': module})

        # Get class Meta options
        meta = nmspc.pop('Meta', None)

        options_class = Options
        if parents:

            def all_parent_names(parents, results=None):
                if not results:
                    results = []

                for p in parents:
                    for b in p.__bases__:
                        results.append(b.__name__)
                        if b.__bases__:
                            all_parent_names(b.__bases__, results)


                return results

            all_parents = all_parent_names(parents)
            all_parents.extend([p.__name__ for p in parents])

            if 'NavModel' in all_parents:
                options_class = NavOptions
        else:
            if name == 'NavModel':
                options_class = NavOptions

        new_cls._meta = options_class(meta)

        for opt in dir(meta):
            if opt.find('__') == -1:
                setattr(new_cls._meta, opt, getattr(meta, opt))

        new_cls._meta._set_endpoints(dict(new_cls._meta._default_endpoints))

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

        # Register the id attribute which will contain all the diferent ids'
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
        #new_cls._meta.add_default_codeunit_page()

        return new_cls


class Model(object):
    __metaclass__ = BaseModel
    client = None
    objects = None

    def __init__(self, *args, **kwargs):
        # Initialize attributes to the field default value
        for field in self._meta.declared_fields:
            setattr(self, field.name, field.default)

        if args:
            # If the model has no custom fields you can't initialize an
            # instance providing only args, otherwise create attributes from
            # the declared_fields_names
            if not self._meta.declared_fields:
                raise TypeError(
                    'You cannot pass args without specifying custom fields.')
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
        if item in self._meta.get_discovered_field_names():
            return None
        else:
            raise AttributeError(item)

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
        # Remove id from the keylist because it's handled from the add_key
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

    def add_id(self, id):
        setattr(self, self._meta.default_id, id)

    def get_id(self):
        if not hasattr(self, self._meta.default_id):
            return

        return getattr(self, self._meta.default_id)

    @require_client
    def save(self):
        """
        Saves or updates the object
        """
        self.clean()
        # Create dict with all the fields (declared and discovered)
        tmp_dict = dict((field, getattr(self, field)) for field in
                        self._meta.get_field_names() if
                        field not in self._meta.readonly_fields)

        # If there is the id just update, otherwise run create
        if self.get_id():
            self.objects.update(obj=self, **tmp_dict)
        else:
            self.objects.create(obj=self, **tmp_dict)

    @require_client
    def delete(self):
        """
        Deletes the object
        """
        return self.objects.delete(obj=self)


class NavModel(Model):
    def __init__(self, *args, **kwargs):
        # Initialize the default_id to an empty list
        setattr(self, self._meta.default_id, [])
        super(NavModel, self).__init__(*args, **kwargs)

    def add_companies(self, companies):
        """
        Add companies to the object
        """
        for company in companies:
            instances = self.get_instances()
            instances.append(Instance(company))

    def get_companies(self):
        """
        Return all the companies for this object
        """
        companies = []
        for instance in self.get_instances():
            if instance.company:
                companies.append(instance.company)

        return companies

    def remove_id(self, id):
        """
        Removes an instance from the default_id attribute
        """
        index = None
        for count, instance in enumerate(self.get_instances()):
            if instance.id == id:
                index = count
                break

        if index is not None:
            isntances = self.get_instances()
            isntances.pop(index)

    def add_id(self, company, client, id):
        """
        Adds an instance at the default_id (for example on get)
        or update a badge's information (for example at the save)
        """
        for instance in self.get_instances():
            if instance.company == company:
                instance.client, instance.id = client, id
                return

        instances = self.get_instances()
        instances.append(Instance(company, id, client))

    def get_id(self):
        """
        Return all the ids for this object
        """
        ids = []
        for instance in self.get_instances():
            if instance.id:
                ids.append(instance.id)

        return ids

    def get_instances(self):
        """
        Returns the instance objects
        """
        return getattr(self, self._meta.default_id)

    def save(self):
        """
        Saves or updates the object
        """
        if len(self.get_companies()) == 0:
            return

        self.clean()
        # Create dict with all the fields (declared and discovered)
        tmp_dict = dict((field, getattr(self, field)) for field in
                        self._meta.get_field_names() if
                        field not in self._meta.readonly_fields)

        # If there wasn't any change at the companies just update, otherwise
        # run create which handles these new companies
        if len(self.get_id()) == len(self.get_companies()):
            self.objects.update(obj=self, **tmp_dict)
        else:
            self.objects.create(obj=self, **tmp_dict)
