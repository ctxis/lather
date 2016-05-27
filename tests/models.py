# -*- coding: utf-8 -*-
from lather import models


class TestModel1(models.Model):
    var1 = models.Field(max_length=30)
    var2 = models.Field()


class TestModel2(models.Model):

    class Meta:
        get = 'Example'


class TestModel3(models.Model):

    class Meta:
        fields = 'all'