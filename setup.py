""" Copyright (c) Trainline Limited, 2016. All rights reserved. See LICENSE.txt in the project root for license information. """
from setuptools import setup

install_requires = ['requests', 'simplejson']

setup(name='environment_manager',
      version='0.0.1',
      description="A Client library for Environment Manager",
      maintainer="Marc Cluet",
      maintainer_email="marc.cluet@thetrainline.com",
      install_requires=install_requires,
      license='Apache 2.0',
      package_data={'': ['LICENSE.txt']},
      packages=['environment_manager'],
      zip_safe=True)
