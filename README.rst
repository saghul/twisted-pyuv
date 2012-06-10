
===============================
A Twisted Reactor based on pyuv
===============================

twisted-pyuv is a Twisted Reactor implementation which uses pyuv
as the networking library instead of any of the builtin reactors.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.

Source code is on `GitHub <http://github.com/saghul/pyuv>`_.


Motivation
==========

This is an experimental project to test pyuv's capabilities with a
big framework such as Twisted. It still doesn't implement all it's
features, but sockets are working :-)


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

