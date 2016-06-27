# -*- coding: utf-8 -*-
import pytest
from lather import models, exceptions, client

from tests import models as test_models
from tests import utils


class TestBaseModel:

    @pytest.fixture(autouse=True)
    def nmspc(self):
        self.base_dict = dict(
            __module__ = '__main__'
        )

    def test_new(self):
        new_class = type('TestModel', (models.Model, ), self.base_dict)

        assert hasattr(new_class, '_meta')
        assert isinstance(new_class._meta, models.Options)
        assert new_class._meta.declared_fields == []
        assert new_class._meta.default_id == 'Key'
        assert new_class._meta.page == 'Page/TestModel'

    def test_mew_with_meta_class(self):
        class Meta:
            get = 'Test'
            page = 'Test'
        nmspc = self.base_dict
        nmspc.update(Meta=Meta)
        new_class = type('TestModel', (models.Model, ), nmspc)

        assert hasattr(new_class, '_meta')
        assert new_class._meta.get == Meta.get
        assert new_class._meta.page == Meta.page

    def test_new_raise_duplicate_key_error(self):
        nmspc = self.base_dict
        nmspc.update(Key=models.Field(max_length=10))

        with pytest.raises(exceptions.FieldException):
            type('TestModel', (models.Model, ), nmspc)

    def test_new_with_fields(self):
        nmspc = self.base_dict
        nmspc.update(var1=models.Field(max_length=10))
        new_class = type('TestModel', (models.Model, ), nmspc)

        assert hasattr(new_class, '_meta')
        assert len(new_class._meta.declared_fields) == 1
        assert len(new_class._meta.discovered_fields) == 0

    def test_new_with_fields_attr(self):
        class Meta:
            fields = 'all'
        nmspc = self.base_dict
        nmspc.update(Meta=Meta)
        new_class = type('TestModel', (models.Model, ), nmspc)
        assert len(new_class._meta.declared_fields) == 0
        assert len(new_class._meta.discovered_fields) == 0

    def test_new_raise_error_about_fields_attr_and_custom_fields_together(self):
        class Meta:
            fields = 'all'
        nmspc = self.base_dict
        nmspc.update(Meta=Meta)
        nmspc.update(var2=models.Field())

        with pytest.raises(exceptions.FieldException):
            type('TestModel', (models.Model, ), nmspc)

    def test_new_inheritance_with_no_extra_fields(self):
        new_class = type('TestModel', (test_models.TestModel1, ),
                         self.base_dict)

        assert len(new_class._meta.declared_fields) == 2

    def test_new_inheritance_with_extra_fields(self):
        nmspc = self.base_dict
        nmspc.update(var3=models.Field(max_length=10))
        new_class = type('TestModel', (test_models.TestModel1, ), nmspc)

        assert len(new_class._meta.declared_fields) == 3

    def test_new_inheritance_with_extra_fields_with_the_same_name(self):
        nmspc = self.base_dict
        nmspc.update(var1=models.Field(max_length=10))

        with pytest.raises(Exception):
            new_class = type('TestModel', (test_models.TestModel1,), nmspc)

    def test_new_inheritance_with_two_parents(self):
        new_parent = type('TestParent', (models.Model, ),
                          self.base_dict.copy())
        new_class = type('TestModel', (new_parent, test_models.TestModel1),
                         self.base_dict.copy())

        assert len(new_class._meta.declared_fields) == 2

    def test_new_inheritance_with_conflicts_at_the_parents(self):
        nmspc = self.base_dict.copy()
        nmspc.update(var1=models.Field(max_length=10))
        new_parent = type('TestParent', (models.Model, ), nmspc)
        with pytest.raises(exceptions.FieldException):
            new_class = type('TestModel', (new_parent, test_models.TestModel1),
                             self.base_dict.copy())

    def test_new_inheritance_from_non_model_class(self):
        #TODO: Test for #248 models.py doesn't work
        new_parent = type('TestParent', (object, ), {})
        new_class = type('TestModel', (new_parent, models.Model),
                         self.base_dict)

        assert new_class

    def test_new_inheritance_with_new_meta_attributes_1(self):
        class Meta:
            get = 'Test'
        nmspc = self.base_dict
        nmspc.update(Meta=Meta)
        new_class = type('TestModel', (test_models.TestModel1, ), nmspc)

        assert new_class._meta.get == Meta.get

    def test_new_inheritance_with_new_meta_attributes_2(self):
        class Meta:
            get = 'Test'
        nmspc = self.base_dict
        nmspc.update(Meta=Meta)
        new_class = type('TestModel', (test_models.TestModel2, ), nmspc)

        assert new_class._meta.get == Meta.get


class TestModel:

    @pytest.fixture(autouse=True)
    def nmspc(self):
        self.data = dict(
            var1='Test',
            var2='Test',
        )
        self.keylist = ['var1', 'var2']

    def test_init(self):
        inst = test_models.TestModel1(var1='Test')
        assert inst.var1 == 'Test'
        for field in inst._meta.declared_fields:
            if field.name != 'var1':
                assert getattr(inst, field.name) == field.default

    def test_init_with_fields_attr_and_args_1(self):
        with pytest.raises(TypeError):
            inst = test_models.TestModel3('Args1', 'Args2')

    def test_init_with_fields_attr_and_args_2(self):
        inst = test_models.TestModel1('Args1', 'Args2')

        assert inst.var1 == 'Args1'
        assert inst.var2 == 'Args2'

    def test_init_with_fields_attr_and_args_3(self):
        with pytest.raises(TypeError):
            inst = test_models.TestModel1('Args1', 'Args2', 'Args3')

    def test_init_with_kwargs_1(self):
        inst = test_models.TestModel1(var1='Args1', var2='Args2')

        assert inst.var1 == 'Args1'
        assert inst.var2 == 'Args2'

    def test_init_with_kwargs_2(self):
        with pytest.raises(TypeError):
            inst = test_models.TestModel1(var='Args1')

    def test_init_with_kwargs_3(self):
        inst = test_models.TestModel3(var_test_1='Args1', var_test_2='Args2')

        assert len(inst._meta.declared_fields) == 2
        assert len(inst._meta.discovered_fields) == 0
        assert inst.var_test_1 == 'Args1'
        assert inst.var_test_2 == 'Args2'

    def test_populate_attrs_with_same_fields(self):
        response = utils.Response(keylist=self.keylist, dict=self.data)
        inst = test_models.TestModel1()
        inst.populate_attrs(response)

        for field in inst._meta.declared_fields:
            assert getattr(inst, field.name) == self.data[field.name]
        assert len(inst._meta.discovered_fields) == 0

    def test_populate_attrs_with_extra_fields(self):
        data = self.data
        data.update(var3='Test')
        keylist = self.keylist
        keylist.append('var3')
        response = utils.Response(keylist=keylist, dict=data)
        inst = test_models.TestModel1()
        inst.populate_attrs(response)

        for field in inst._meta.declared_fields:
            assert getattr(inst, field.name) == self.data[field.name]
        assert len(inst._meta.discovered_fields) == 1
        assert hasattr(inst, 'var3')

    def test_populate_attrs_with_less_fields(self):
        """
        For this test we will create a new class because we want to exam
        the discovered_fields and we will use inheritance
        """
        data = self.data
        data.pop('var2', None)
        keylist = self.keylist
        keylist.pop(keylist.index('var2'))

        response = utils.Response(keylist=keylist, dict=data)
        new_class = type('TestModel', (test_models.TestModel1, models.Model, ),
                         {'__module__': '__main__'})
        inst = new_class()
        inst.populate_attrs(response)

        for field in inst._meta.declared_fields:
            if field.name != 'var2':
                assert getattr(inst, field.name) == self.data[field.name]
            elif field.name == 'var2':
                assert field._blank is True
        assert len(inst._meta.discovered_fields) == 0

    def test_eq_1(self):
        inst1 = test_models.TestModel1('Args1', 'Args2')
        inst2 = test_models.TestModel1('Args1', 'Args2')

        assert inst1 == inst2

    def test_get_companies(self):
        companies = ['Company1', 'Company2']
        inst = test_models.TestModel2()
        inst.add_companies(companies)

        assert inst.get_companies() == companies


@pytest.mark.usefixtures("mock")
class TestQueryset:

    @pytest.fixture
    def customer_model(self):
        class Meta:
            fields = 'all'

        nmspc = {
            '__module__': '__main__',
            'Meta': Meta
        }

        return type('Customer', (models.Model, ), nmspc)

    @pytest.fixture
    def queryset(self, customer_model):
        latherclient = client.LatherClient('test', cache=None)
        latherclient.register(customer_model)
        return models.QuerySet(customer_model.objects, customer_model)

## Test get

    def test_get(self, queryset):
        customer = queryset.get(No='Test')

        assert isinstance(customer.Key, list)
        assert len(customer.Key) == 4
        for key in customer.Key:
            assert isinstance(key, models.Key)
        assert customer.Key[0].key == 'Key'
        assert customer._meta.declared_fields == []
        assert len(customer._meta.discovered_fields) == 2

    def test_get_raise_objectnotfound(self, queryset):
        queryset.model._meta.get = 'Read_NotFound'
        with pytest.raises(exceptions.ObjectDoesNotExist):
            queryset.get(No='Test')

    def test_get_return_multiple_objs_1(self, queryset):
        queryset.model._meta.get = 'Read_Diff'
        customer = queryset.get(No='Test')
        customers = [c for c in customer]

        assert isinstance(customer, models.QuerySet)
        assert len(customer.queryset) == 2
        assert len(customers[0].Key) == 3
        assert customers[1].Name == 'Test_Diff'
        assert len(customers[1].Key) == 1
        assert customers[0].Name == 'Test'

    def test_get_return_multiple_objs_2(self, queryset):
        queryset.model._meta.get = 'Read_Diff'
        customer = queryset.get(No='Test')
        customers = [c for c in customer]

        assert len(customers[0].Key) == 3
        assert customers[0].Key[0].key == 'Key0'
        assert customers[0].Key[2].key == 'Key1'

    def test_get_raise_error_providing_false_kwargs(self, queryset):
        with pytest.raises(AttributeError):
            customer = queryset.get(Test='Test')

    def test_get_raise_error_providing_wrong_number_of_kwargs(self, queryset):
        with pytest.raises(AttributeError):
            customer = queryset.get(No='Test', Name='Test')

    def test_get_raise_error_without_lather_client(self):
        # Use the TestModel3 because the Customer model
        # contain already a client so we will not see the raise
        manager = models.Manager(test_models.TestModel3)
        queryset = models.QuerySet(manager, test_models.TestModel3)
        with pytest.raises(Exception):
            customer = queryset.get(No='Test')
        with pytest.raises(Exception):
            customer = queryset.create(No='Test', Name='Test')
        with pytest.raises(Exception):
            customer = queryset.delete(Key='Test')

## Test delete

    def test_delete_providing_key(self, queryset):
        response = queryset.delete(Key='Key')

        assert response

    def test_delete_fail(self, queryset):
        queryset.model._meta.delete = 'Delete_Fail'
        response = queryset.delete(Key='Key')

        assert not response

    def test_delete_providing_key_list(self, queryset):
        customer = queryset.get(No='Test')
        response = queryset.delete(Key=customer.Key)

        assert response

    def test_delete_providing_wrong_key_list(self, queryset):
        customer = queryset.get(No='Test')
        # Append at key attr key which is not Key object
        customer.Key.append('Test')
        with pytest.raises(TypeError):
            queryset.delete(Key=customer.Key)

    def test_delete_providing_key_list_fail(self, queryset):
        queryset.model._meta.delete = 'Delete_Diff'
        customer = queryset.get(No='Test')
        response = queryset.delete(Key=customer.Key)

        assert not response

    def test_delete_without_providing_key(self, queryset):
        with pytest.raises(Exception):
            queryset.delete()

    def test_delete_without_providing_key_with_queryset(self, queryset):
        customer = queryset.get(No='Test')
        response = queryset.delete()

        assert response

    def test_delete_without_providing_key_with_wrong_queryset(self, queryset):
        customer = queryset.get(No='Test')
        # Insert at key attr key which is not Key object
        customer.Key.insert(0, 'Test')
        with pytest.raises(TypeError):
            queryset.delete()

    def test_delete_without_providing_key_with_queryset_fail(self, queryset):
        queryset.model._meta.delete = 'Delete_Diff'
        customer = queryset.get(No='Test')
        response = queryset.delete()

        assert not response

    def test_delete_providing_obj(self, queryset):
        customer = queryset.get(No='Test')
        response = queryset.delete(obj=customer)

        assert response

    def test_delete_providing_obj_fail(self, queryset):
        queryset.model._meta.delete = 'Delete_Diff'
        customer = queryset.get(No='Test')
        response = queryset.delete(obj=customer)

        assert not response

## Test create

    def test_create(self, queryset):
        customer = queryset.create(No='Test', Name='Test')

        assert len(customer.Key) == 4
        assert customer.Key[0].key == 'Key'

    def test_create_providing(self, queryset, customer_model):
        customer_obj = customer_model(No='Test', Name='Test')
        customer_obj.add_companies(['Company1', 'Company2'])

        assert len(customer_obj.Key) == 2
        assert customer_obj.Key[0].key is None
        queryset.create(obj=customer_obj)
        assert len(customer_obj.Key) == 2
        assert customer_obj.Key[0].key == 'Key'

## Test update

    def test_update(self, queryset):
        name = 'Test for example'
        customer = queryset.update(Key='Test', Name=name)

        assert len(customer.Key) == 4
        assert customer.Name == name

    def test_update_without_key(self, queryset):
        with pytest.raises(TypeError):
            queryset.update(Name='Test')

    def test_update_providing_keys(self, queryset):
        name = 'Test for example'
        customer = queryset.get(No='Test')

        assert customer.Name == 'Test'
        new_customer = queryset.update(Key=customer.Key)
        assert len(new_customer.Key) == 4
        assert new_customer.Name == name
        assert new_customer.Key[0].key == 'Key'

    def test_update_providing_object(self, queryset, customer_model):
        name = 'Test for example'
        customer_obj = customer_model(No='Test', Name='Test')
        customer_obj.add_companies(['Company1', 'Company2'])

        assert len(customer_obj.Key) == 2
        assert customer_obj.Key[0].key is None
        assert customer_obj.Name == 'Test'
        queryset.update(obj=customer_obj, Name=name)
        assert len(customer_obj.Key) == 2
        assert customer_obj.Key[0].key == 'Key'
        assert customer_obj.Name == name

## Test get_or_create

    def test_get_or_create_get(self, queryset):
        customer, created = queryset.get_or_create(No='Test',
                                                  defaults={'Name': 'Test'})
        assert not created

    def test_get_or_create_create(self, queryset):
        queryset.model._meta.get = 'Read_NotFound'
        customer, created = queryset.get_or_create(No='Test',
                                                   defaults={'Name': 'Test'})
        assert created

    def test_get_or_create_create_with_duplicate_keys(self, queryset):
        queryset.model._meta.get = 'Read_NotFound'
        with pytest.raises(AttributeError):
            queryset.get_or_create(No='Test', defaults={'No': 'Test'})

    def test_get_or_create_with_declared_fields(self, queryset):
        queryset.model._meta.get = 'Read_NotFound'
        queryset.model._meta.declared_fields.extend([
            models.Field(name='No'),
            models.Field(name='Name')
        ])
        with pytest.raises(AttributeError):
            queryset.get_or_create(No='Test', defaults={'Test': 'Test'})

    def test_get_or_create_without_defaults(self, queryset):
        with pytest.raises(Exception):
            queryset.get_or_create(No='Test')

## filter

    def test_filter(self, queryset):
        response = queryset.filter(No='Test*')

        assert isinstance(response, models.QuerySet)
        assert response.queryset[0].Name == 'Test'
        assert response.queryset[1].Name == 'Test for example'
        assert response.queryset[2].Name == 'Test3 for example'

## len

    def test_len(self, queryset):
        response = queryset.filter(No='Test*')

        assert len(response) == 3

## iter

    def test_iter(self, queryset):
        response = queryset.filter(No='Test*')

        for result in response:
            assert isinstance(result, models.Model)

    def test_iter_without_queryset(self, queryset):
        queryset.create(No='Test', Name='Test')
        with pytest.raises(Exception):
            results = [result for result in queryset]

## count

    def test_count(self, queryset):
        queryset.get(No='Test')

        assert queryset.count() == 1

    def test_count_without_queryset(self, queryset):
        queryset.create(No='Test', Name='Test')
        with pytest.raises(Exception):
            queryset.count()



class TestField:

    def test_repr_without_name(self):
        field = models.Field()

        assert repr(field) == '<lather.models.Field>'

    def test_repr_with_name(self):
        field = models.Field(name='Field')

        assert repr(field) == '<lather.models.Field: Field>'

    def test_run_validators_raise_exception_1(self):
        field = models.Field(validators=[utils.MaxLengthValidaiton(5)])

        with pytest.raises(exceptions.ValidationError) as e:
            field.run_validators('testing')
        assert e.value.message[0] == 'Max length reached'

    def test_run_validators_raise_exception_2(self):
        field = models.Field()
        field._validators.append(utils.MaxLengthValidaiton(5))

        with pytest.raises(exceptions.ValidationError) as e:
            field.run_validators('testing')
        assert e.value.message[0] == 'Max length reached'

    def test_run_validators_not_raise_exception(self):
        field = models.Field(validators=[utils.MaxLengthValidaiton(10)])
        try:
            field.run_validators('testing')
        except exceptions.ValidationError:
            pytest.fail('Raised unexcpected ValidationError.')

    def test_clean_with_no_validators(self):
        field = models.Field()

        assert field.clean('testing') == 'testing'

    def test_clean_with_validators(self):
        field = models.Field(validators=[utils.MaxLengthValidaiton(5)])

        with pytest.raises(exceptions.ValidationError) as e:
            field.clean('testing')
        assert e.value.message[0] == 'Max length reached'
