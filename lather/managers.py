# -*- coding: utf-8 -*-
import logging

from .decorators import require_client
from .decorators import require_default
from .exceptions import ObjectDoesNotExist
from .exceptions import ObjectsDoNotExist
from .exceptions import MultipleObjectReturned

from suds import WebFault

log = logging.getLogger('lather_client')


class Instance(object):
    def __init__(self, company, id=None, client=None):
        self.company = company
        self.id = id
        self.client = client

    def __repr__(self):
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        id = getattr(self, 'id', None)
        company = getattr(self, 'company', None)
        if id is not None and company is not None:
            return '<%s: (%s, %s)>' % (path, company, id)
        return '<%s>' % path


class BaseQuerySet(object):
    def __init__(self, manager, model):
        self.manager = manager
        self.model = model
        self.queryset = None
        self.client = self._connect()

    def __len__(self):
        return self.count()

    def __iter__(self):
        if not self.queryset:
            raise Exception('No queryset found')

        return iter(self.queryset)

    def __getitem__(self, item):
        if not self.queryset:
            raise Exception('No queryset found')

        return self.queryset[item]

    def __repr__(self):
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        queryset = getattr(self, 'queryset', None)
        if queryset:
            if self.count() >= 10:
                return "[%s '...(remaining elements truncated)...']" \
                       % ', '.join([str(r) for r in queryset])
            else:
                return '[%s]' % ', '.join([str(r) for r in queryset])
        return '<%s>' % path

    def _connect(self, *args, **kwargs):
        """
        Central method which makes the connection to the api
        """
        page = self.model._meta.page
        return self.model.client.connect(page, *args, **kwargs)

    def _query(self, client, method, **kwargs):
        """
        Central method which executes the api calls
        """
        if not method:
            raise TypeError('Method must be a string not None.')
        if kwargs.get('attrs', None):
            return getattr(client, method)(kwargs.get('attrs'))
        return getattr(client, method)(**kwargs)

    def _check_kwargs(self, method, **kwargs):
        page = self.model._meta.page
        params = self.model.client.get_service_params(method, page)

        # Because elements are suds.sax.text.Text, convert them to str
        params = [str(x[0]) for x in params]
        if params:
            if len(kwargs.keys()) > len(params):
                raise AttributeError('You have specified too many arguments.')
            for k in params:
                if k not in kwargs.keys():
                    raise AttributeError('You have to specify the arg: %s' % k)

    def _create_inst(self, response, obj=None):
        if obj:
            obj.populate_attrs(response)
            obj.add_id(getattr(response, self.model._meta.default_id))
            return

        inst = self.model()
        inst.populate_attrs(response)
        inst.add_id(getattr(response, self.model._meta.default_id))
        return inst

    def _get_response_id(self, response):
        return getattr(response, self.model._meta.default_id)

    @require_client
    def create(self, **kwargs):
        attrs = dict(attrs=kwargs)
        return self._query(self.client, self.model._meta.create, **attrs)

    @require_client
    def update(self, **kwargs):
        attrs = dict(attrs=kwargs)
        return self._query(self.client, self.model._meta.update, **attrs)

    @require_client
    def get(self, **kwargs):
        # When the result is None the suds raise AttributeError, handle
        # this error to return ObjectNotFound
        try:
            response = self._query(self.client, self.model._meta.get, **kwargs)
        except AttributeError:
            raise ObjectDoesNotExist('Object not found')

        if isinstance(response, list):
            raise MultipleObjectReturned('This function can return only one '
                                         'object but the query returned '
                                         'multiple results. Use all instead')

        return response

    @require_client
    def delete(self, **kwargs):
        id = kwargs.get(self.model._meta.default_id, None)
        if not id:
            raise Exception('You have to provide a keyword: %s'
                            % self.model._meta.default_id)

        if not self._query(self.client, self.model._meta.delete, **kwargs):
            return False

        return True

    @require_client
    def all(self):
        return iter(self._query(self.client, self.model._meta.all))

    @require_client
    def filter(self, **kwargs):
        params = self.client.get_service_params(self.model._meta.filter)

        filters = []
        for k in kwargs.keys():
            filter = self.client.factory(params[0][1].type[0])
            setattr(filter, 'Field', k)
            setattr(filter, 'Criteria', kwargs.get(k))
            filters.append(filter)

        # TODO: Try pipe filters
        try:
            response = iter\
                (getattr(self.client, self.model._meta.filter)(filters)[0])
        except IndexError:
            raise ObjectsDoNotExist('Objects not found')

        return response

    def count(self):
        """
        Return the number of the results if the queryset exists
        """
        if not self.queryset:
            raise Exception('No queryset found')

        return len(list(self.queryset))


class QuerySet(BaseQuerySet):

    @require_client
    def create(self, obj=None, **kwargs):
        response = super(QuerySet, self).create(**kwargs)

        if obj:
            self._create_inst(response, obj)
        else:
            return self._create_inst(response)

    @require_client
    def update(self, obj=None, **kwargs):
        if obj:
            if self.queryset:
                for inst in self.queryset:
                    kwargs.update({self.model._meta.default_id:
                                       getattr(inst, self.model._meta.default_id)})
                    attrs = dict(attrs=kwargs)
                    response = super(QuerySet, self).update(**attrs)
                    self._create_inst(response, obj)
            else:
                kwargs.update({self.model._meta.default_id:
                                   getattr(obj, self.model._meta.default_id)})
                attrs = dict(attrs=kwargs)
                response = super(QuerySet, self).update(**attrs)
                self._create_inst(response, obj)
        else:
            attrs = dict(attrs=kwargs)
            response = super(QuerySet, self).update(**attrs)
            return self._create_inst(response)

    @require_client
    def get(self, **kwargs):
        #TODO: The following line cause one request more
        #self._check_kwargs(self.model._meta.get, **kwargs)

        self.queryset = []

        response = super(QuerySet, self).get(**kwargs)

        inst = self._create_inst(response)
        self.queryset.append(inst)

        return inst

    @require_client
    def delete(self, obj=None, **kwargs):
        if obj:
            kwargs = { self.model._meta.default_id:
                             getattr(obj, self.model._meta.default_id) }

        return super(QuerySet, self).delete(**kwargs)

    @require_client
    def all(self):
        self.queryset = []
        response = super(QuerySet, self).all()

        for r in response:
            self.queryset.append(self._create_inst(r))

        return self

    @require_client
    @require_default
    def get_or_create(self, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
        # Sometimes, the returning object doesn't contain all the attributes
        # from the defaults so if you specify a new value to an attribute
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
            duplicate_keywords = []
            non_declared_fields = []
            for keyword in defaults.keys():
                if keyword in kwargs.keys():
                    duplicate_keywords.append(keyword)
                if self.model._meta.declared_fields:
                    if keyword not in self.model._meta.get_declared_field_names():
                        non_declared_fields.append(keyword)

            if duplicate_keywords:
                raise AttributeError('Duplicate keywords at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keywords))

            if non_declared_fields:
                raise AttributeError('Some of the keys are not specified '
                                     'at the fields: %s'
                                     % ', '.join(non_declared_fields))
            kwargs.update(defaults)
            inst = self.create(**kwargs)
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
            self.update(inst, **defaults)
            created = False
        except ObjectDoesNotExist:
            # Update the defaults with the kwargs which contains the query
            # fields
            duplicate_keywords = []
            non_declared_fields = []
            for keyword in defaults.keys():
                if keyword in kwargs.keys():
                    duplicate_keywords.append(keyword)
                if self.model._meta.declared_fields:
                    if keyword not in self.model._meta.get_declared_field_names():
                        non_declared_fields.append(keyword)

            if duplicate_keywords:
                raise AttributeError('Duplicate keywords at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keywords))

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
        response = super(QuerySet, self).filter(**kwargs)
        for result in response:
            inst = self._create_inst(response)
            self.queryset.append(inst)

        return self


class NavQuerySet(BaseQuerySet):
    def __init__(self, manager, model):
        self.manager = manager
        self.model = model
        self.queryset = None

    @require_client
    def create(self, obj=None, companies=None, **kwargs):
        if obj:
            # Send the create action to the appropriate companies
            for instance in obj.get_instances():
                # If the instance object contains the id attribute then came
                # from the update_or_create() -> update() -> create() because
                # the user added some new companies, so the object contains
                # some instance objects with id
                if instance.id:
                    continue
                self.client = instance.client
                if not self.client:
                    self.client = self._connect(instance.company)

                response = super(NavQuerySet, self).create(**kwargs)
                obj.populate_attrs(response)
                obj.add_id(instance.company, self.client,
                            self._get_response_id(response))
        else:
            inst = None
            if not companies:
                companies = self.model.client.companies
            for company in companies:
                self.client = self._connect(company)
                response = super(NavQuerySet, self).create(**kwargs)
                if not inst:
                    inst = self.model()
                    inst.populate_attrs(response)
                inst.add_id(company, self.client,
                             self._get_response_id(response))

            return inst

    @require_client
    def update(self, obj=None, companies=None, delete=False, **kwargs):
        if obj:
            # This if will be true when the previous function is the
            # update_or_create
            if self.queryset:
                existing_companies = []
                for inst in self.queryset:
                    # Finally we will have:
                    # add_companies: contains new companies and will create
                    # update_companies: contains existing companies and will update
                    # delete_companies: contains deleted companies and will delete
                    add_companies = []
                    existing_companies.extend(inst.get_companies())
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

                    new_add_companies = add_companies[:]
                    for company in add_companies:
                        for inst2 in self.queryset:
                            if company in inst2.get_companies():
                                if company not in update_companies:
                                    update_companies.append(company)
                                new_add_companies.pop(new_add_companies.index(company))

                    add_companies = new_add_companies[:]


                    for instance in inst.get_instances():
                        if instance.company in update_companies:
                            kwargs.update(
                                { self.model._meta.default_id: instance.id })
                            #self.client = instance.client
                            #if not self.client:
                            self.client = self._connect(instance.company)

                            response = super(NavQuerySet, self).update(**kwargs)
                            inst.populate_attrs(response)
                            inst.add_id(instance.company, self.client,
                                         self._get_response_id(response))
                        elif instance.company in delete_companies:
                            if isinstance(delete, dict):
                                delete.update(
                                    { self.model._meta.default_id: instance.id })
                                #self.client = instance.client
                                #if not self.client:
                                self.client = self._connect(instance.company)

                                response = super(NavQuerySet, self).update(**delete)
                                inst.remove_id(instance)
                            if delete == True:
                                tmp_dict = {self.model._meta.default_id:
                                                str(instance.id)}
                                self.delete(**tmp_dict)
                                inst.remove_id(instance)
                    # Now create the new entries
                    if add_companies:
                        inst.add_companies(add_companies)
                        inst.save()
            else:
                for instance in obj.get_instances():
                    kwargs.update({self.model._meta.default_id: instance.id})
                    self.client = instance.client
                    if not self.client:
                        self.client = self._connect(instance.company)

                    response = super(NavQuerySet, self).update(**kwargs)
                    obj.populate_attrs(response)
                    obj.add_id(instance.company, self.client,
                                self._get_response_id(response))
        else:
            inst = None
            ids = kwargs.pop(self.model._meta.default_id, None)
            if not ids:
                raise TypeError("You have to provide a keyword: %s"
                                % self.model._meta.default_id)

            if isinstance(ids, list):
                for instance in ids:
                    if not isinstance(instance, Instance):
                        raise TypeError('The list must contain Key objects')

                    self.client = instance.client
                    if not self.client:
                        self.client = self._connect(instance.company)
                    kwargs.update({self.model._meta.default_id: instance.id})
                    response = super(NavQuerySet, self).update(**kwargs)
                    if not inst:
                        inst = self.model()
                        inst.populate_attrs(response)
                    inst.add_id(instance.company, self.client,
                                 self._get_response_id(response))
            else:
                # TODO: Does not work for some reason, maybe needs the company
                if not companies:
                    companies = self.model.client.companies
                skipped = 0
                for company in companies:
                    self.client = self._connect(company)
                    kwargs.update({self.model._meta.default_id: ids})
                    # because whenever tries to update something which
                    # doesn't exist raise this error
                    try:
                        response = super(NavQuerySet, self).update(**kwargs)
                    except WebFault:
                        skipped += 1
                        continue

                    if not inst:
                        inst = self.model()
                        inst.populate_attrs(response)
                    inst.add_id(company, self.client,
                                 self._get_response_id(response))

                if skipped == len(companies):
                    raise ObjectDoesNotExist('Object not found')

            return inst

    @require_client
    def get(self, **kwargs):
        #TODO: The following line cause one request more
        #self._check_kwargs(self.model._meta.get, **kwargs)

        self.queryset = []
        companies = self.model.client.companies
        for company in companies:
            self.client = self._connect(company)
            try:
                response = super(NavQuerySet, self).get(**kwargs)
            except ObjectDoesNotExist:
                continue

            inst = self.model()
            inst.populate_attrs(response)
            inst.add_id(company, self.client, self._get_response_id(response))

            if self.queryset:
                found = False
                for obj in self.queryset:
                    # TODO: Test keys (if are the same at all companies ) and
                    # TODO: give Warning about this
                    if inst == obj:
                        obj_keys = obj.get_instances()
                        inst_keys = inst.get_instances()
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
    def delete(self, obj=None, companies=None, **kwargs):
        success = True
        if obj:
            # Send the delete action to the appropriate companies
            for instance in obj.get_instances():
                self.client = instance.client
                if not self.client:
                    self.client = self._connect(instance.company)
                tmp_dict = {self.model._meta.default_id: instance.id}
                if not super(NavQuerySet, self).delete(**tmp_dict):
                    success = False
        else:
            # Send the delete action to all the companies
            ids = kwargs.get(self.model._meta.default_id, None)
            if self.queryset and not ids:
                tmp_list = self.queryset[:]
                for inst in self.queryset:
                    success = True
                    for instance in inst.get_instances():
                        if not isinstance(instance, Instance):
                            raise TypeError(
                                'The list must contain Key objects')
                        self.client = instance.client
                        if not self.client:
                            self.client = self._connect(instance.company)
                        tmp_dict = {self.model._meta.default_id: instance.id}
                        if not super(NavQuerySet, self).delete(**tmp_dict):
                            success = False
                    if success:
                        tmp_list.pop(tmp_list.index(inst))
                # Assign the undeleted objects
                self.queryset = tmp_list[:]
            else:
                if not ids:
                    raise Exception('You have to provide a keyword: %s'
                                    % self.model._meta.default_id)

                if isinstance(ids, list):
                    for instance in ids:
                        if not isinstance(instance, Instance):
                            raise TypeError(
                                'The list must contain Key objects')
                        self.client = instance.client
                        if not self.client:
                            self.client = self._connect(instance.company)
                        tmp_dict = {self.model._meta.default_id: instance.id}
                        if not super(NavQuerySet, self).delete(**tmp_dict):
                            success = False

                else:
                    if not companies:
                        companies = self.model.client.companies
                    skipped = 0
                    for company in companies:
                        self.client = self._connect(company)
                        # because whenever tries to delete something which
                        # doesn't exist raise this error
                        try:
                            if not super(NavQuerySet, self).delete(**kwargs):
                                success = False
                        except WebFault:
                            skipped += 1
                            continue

                    if skipped == len(companies):
                        success = False
        return success

    @require_client
    def all(self):
        raise NotImplemented("Nav doesn't support any method which returns "
                             "all objects")

    @require_client
    @require_default
    def get_or_create(self, companies=None, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
        # Sometimes, the returning object doesn't contain all the attributes
        # from the defaults so if you specify a new value to an attribute
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
            duplicate_keywords = []
            non_declared_fields = []
            for keyword in defaults.keys():
                if keyword in kwargs.keys():
                    duplicate_keywords.append(keyword)
                if self.model._meta.declared_fields:
                    if keyword not in self.model._meta.get_declared_field_names():
                        non_declared_fields.append(keyword)

            if duplicate_keywords:
                raise AttributeError('Duplicate keywords at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keywords))

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
    def update_or_create(self, companies=None, delete=False, **kwargs):
        created = False
        defaults = kwargs.pop('defaults', None)
        # Same as above
        if not self.model._meta.declared_fields:
            self.model._meta.add_declared_fields_from_names(defaults.keys())

        try:
            inst = self.get(**kwargs)
            self.update(inst, companies, delete, **defaults)
            created = False
        except ObjectDoesNotExist:
            # Update the defaults with the kwargs which contains the query
            # fields
            duplicate_keywords = []
            non_declared_fields = []
            for keyword in defaults.keys():
                if keyword in kwargs.keys():
                    duplicate_keywords.append(keyword)
                if self.model._meta.declared_fields:
                    if keyword not in self.model._meta.get_declared_field_names():
                        non_declared_fields.append(keyword)

            if duplicate_keywords:
                raise AttributeError('Duplicate keywords at kwargs and defaults: '
                                     '%s' % ', '.join(duplicate_keywords))

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
            self.client = self._connect(company)
            try:
                response = super(NavQuerySet, self).filter(**kwargs)
            except ObjectsDoNotExist:
                continue

            for result in response:
                log.debug('[%s] From the company %s we got the result: %s'
                          % (log.name.upper(), company, result))
                inst = self.model()
                inst.populate_attrs(result)
                inst.add_id(company, self.client,
                             self._get_response_id(result))

                if self.queryset:
                    found = False
                    for obj in self.queryset:
                        if inst == obj:
                            obj_keys = obj.get_instances()
                            inst_keys = inst.get_instances()
                            obj_keys.extend(inst_keys)
                            found = True

                    if not found:
                        self.queryset.append(inst)
                else:
                    self.queryset.append(inst)

        return self


class Manager(object):
    queryset_class = QuerySet

    def __init__(self, model):
        self.model = model

    def __getattr__(self, item):
        log.debug('[%s] Calling manager __getattr__: %s' % (log.name.upper(),
                                                            item))
        if hasattr(self.queryset_class, item):
            def wrapper(*args, **kwargs):
                log.debug('[%s] called with %r and %r' % (log.name.upper(),
                                                          args, kwargs))
                queryset = self.queryset_class(self, self.model)
                func = getattr(queryset, item)
                return func(*args, **kwargs)

            return wrapper
        raise AttributeError(item)


class NavManager(Manager):
    queryset_class = NavQuerySet
