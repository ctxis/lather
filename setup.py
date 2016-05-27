import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='lather',
    version='0.1',
    packages=['lather'],
    include_package_data=True,
    license='BSD License',
    description='A simple library for interaction with SOAP APIs.',
    long_description=README,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'suds==0.4',
        'python-ntml3'
    ],
    dependency_links=[
        "https://github.com/ctxis/python-ntlm3.git"
    ]
)

