
===============================
A Twisted Reactor based on pyuv
===============================

twisted-pyuv is a `Twisted <http://www.twistedmatrix.com/>`_ Reactor implementation
which uses `pyuv <http://github.com/saghul/pyuv>`_ as the networking library instead
of any of the builtin reactors.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.


Motivation
==========

This is an experimental project to test pyuv's capabilities with a
big framework such as Twisted.


Installation
============

twisted-pyuv requires pyuv >= 0.10.0.

::

    pip install -U pyuv
    pip install twisted
    python setup.py install


Using it
========

In order to use twisted-pyuv, Twisted needs to be instructed to use
our reactor. In order to do that add the following lines at the beginning
of your project, before importing anything from Twisted:

::

    import twisted_pyuv
    twisted_pyuv.install()


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>


License
=======

tornado-pyuv uses the MIT license, check LICENSE file.

