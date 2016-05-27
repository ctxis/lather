# -*- coding: utf-8 -*-


def require_client(func):
    def wrapper(*args, **kwargs):
        if args[0].__class__.__name__ == 'QuerySet':
            if args[0].model.client:
                return func(*args, **kwargs)
            else:
                raise Exception('Client not found')
        else:
            if args[0].client:
                return func(*args, **kwargs)
            else:
                raise Exception('Client not found')
    return wrapper


# TODO: Needs work
'''def require_key(func):
    def wrapper(*args, **kwargs):
        if not kwargs.get(args[0].model._meta.default_id):
            raise Exception('Primary key not found: %s',
                            args[0].model._meta.default_id)
        else:
            return func(*args, **kwargs)
    return wrapper'''


def require_default(func):
    def wrapper(*args, **kwargs):
        if not kwargs.get('defaults'):
            raise Exception('This function require an argument with name '
                            'defaults')
        else:
            return func(*args, **kwargs)
    return wrapper