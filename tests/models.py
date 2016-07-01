# -*- coding: utf-8 -*-
from lather import models


class TestModel1(models.NavModel):
    var1 = models.Field(max_length=30)
    var2 = models.Field()


class TestModel2(models.NavModel):

    class Meta:
        get = 'Example'


class TestModel3(models.NavModel):

    class Meta:
        fields = 'all'