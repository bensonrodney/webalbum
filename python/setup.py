#!/usr/bin/env python3
from os import environ
from setuptools import setup, find_packages
from setup_requires import runtime_requires, testing_requires

VERSION = '0.0.1'
DESCRIPTION = 'Webalbum utilities to help manage new images into the webalbum.'
LONG_DESCRIPTION = ''

requires = runtime_requires
if environ.get('_TESTING', "").lower() == 'true':
    requires += testing_requires

setup(
    name="qr",
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author="Jason Milen",
    author_email="jpmilen@gmail.com",
    license='MIT',
    packages=find_packages(),
    entry_points = {
        'console_scripts': [
            'latest-from-cam3=webalbum.latest_from_cam3:main',
            'photocopy3=webalbum.photocopy3:main',
        ],
    },
    scripts=[],
    install_requires=requires,
    keywords='conversion',
    classifiers= [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        'License :: OSI Approved :: MIT License',
        "Programming Language :: Python :: 3",
    ]
)
