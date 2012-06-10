# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name             = 'twisted-pyuv',
    version          = '0.2.0',
    url              = 'https://github.com/saghul/twisted-pyuv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    description      = 'Twisted Reactor implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['twisted_pyuv'],
    install_requires = ['pyuv>=0.7.2', 'twisted'],
    platforms        = ['POSIX'],
    classifiers      = [
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: POSIX",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.0",
          "Programming Language :: Python :: 3.1",
          "Programming Language :: Python :: 3.2"
    ]
)

