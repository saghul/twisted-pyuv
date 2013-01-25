
from __future__ import absolute_import, with_statement

import functools
import logging
import threading
import time

import pyuv

from collections import deque
from twisted.internet.base import _SignalReactorMixin
from twisted.internet.posixbase import PosixReactorBase
from twisted.internet.interfaces import IReactorFDSet, IDelayedCall, IReactorTime
from twisted.python import failure, log
from twisted.internet import error
from zope.interface import implements


class UVWaker(object):
    def __init__(self, reactor):
        self._async = pyuv.Async(reactor._loop, lambda x: None)
        self._async.unref()
    def wakeUp(self):
        self._async.send()


class UVDelayedCall(object):
    implements(IDelayedCall)

    def __init__(self, reactor, seconds, f, *args, **kw):
        self._reactor = reactor
        self._func = functools.partial(f, *args, **kw)
        self._time = self._reactor.seconds() + seconds
        self._timer = pyuv.Timer(self._reactor._loop)
        self._timer.start(self._called, self._time-self._reactor.seconds(), 0.0)
        self._active = True

    def _called(self, handle):
        self._active = False
        self._timer.stop()
        self._reactor._removeDelayedCall(self)
        try:
            self._func()
        except Exception:
            logging.error("_called caught exception", exc_info=True)

    def getTime(self):
        return self._time

    def cancel(self):
        self._active = False
        self._timer.stop()
        self._reactor._removeDelayedCall(self)

    def delay(self, seconds):
        self._timer.stop()
        self._time += seconds
        self._timer.start(self._called, self._time-self._reactor.seconds(), 0.0)

    def reset(self, seconds):
        self._timer.stop()
        self._time = self._reactor.seconds() + seconds
        self._timer.start(self._called, self._time-self._reactor.seconds(), 0.0)

    def active(self):
        return self._active

class UVReactor(PosixReactorBase):
    implements(IReactorTime, IReactorFDSet)

    def __init__(self):
        self._loop = pyuv.Loop()
        self._signal_watcher = pyuv.Signal(self._loop)
        self._async_handle = pyuv.Async(self._loop, self._async_cb)
        self._async_handle_lock = threading.Lock()
        self._async_callbacks = deque()
        self._readers = {}  # map of reader objects to fd
        self._writers = {}  # map of writer objects to fd
        self._fds = {}      # map of fd to a (reader, writer) tuple
        self._delayedCalls = {}
        self._poll_handles = {}
        PosixReactorBase.__init__(self)

    def _get_loop_handles(self):
        handles = set()
        def cb(handle):
            if not handle.closed:
                handles.add(handle)
        self._loop.walk(cb)
        return handles

    # IReactorTime
    def seconds(self):
        return time.time()

    def callLater(self, seconds, f, *args, **kw):
        dc = UVDelayedCall(self, seconds, f, *args, **kw)
        self._delayedCalls[dc] = True
        return dc

    def getDelayedCalls(self):
        return [x for x in self._delayedCalls if x._active]

    def _removeDelayedCall(self, dc):
        if dc in self._delayedCalls:
            del self._delayedCalls[dc]

    def _async_cb(self, handle):
        with self._async_handle_lock:
            callbacks = self._async_callbacks
            self._async_callbacks = deque()
        while callbacks:
            cb = callbacks.popleft()
            try:
                cb()
            except Exception:
                log.err()

    # IReactorThreads

    def callFromThread(self, f, *args, **kw):
        """See `twisted.internet.interfaces.IReactorThreads.callFromThread`"""
        assert callable(f), "%s is not callable" % f
        cb = functools.partial(f, *args, **kw)
        with self._async_handle_lock:
            self._async_callbacks.append(cb)
        self._async_handle.send()

    def _handleSignals(self):
        """Bypass installing the child waker"""
        _SignalReactorMixin._handleSignals(self)

    # IReactorProcess

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, uid=None, gid=None, usePTY=0, childFDs=None):
        raise NotImplementedError("spawnProcess")

    def installWaker(self):
        self.waker = UVWaker(self)

    def wakeUp(self):
        if self.waker:
            self.waker.wakeUp()

    def _invoke_callback(self, handle, events, poll_error):
        fd = handle.fd
        reader, writer = self._fds[fd]
        if reader:
            err = None
            if reader.fileno() == -1:
                err = error.ConnectionLost()
            elif events & pyuv.UV_READABLE:
                err = log.callWithLogger(reader, reader.doRead)
            if err is None and poll_error is not None:
                err = error.ConnectionLost()
            if err is not None:
                self.removeReader(reader)
                reader.readConnectionLost(failure.Failure(err))
        if writer:
            err = None
            if writer.fileno() == -1:
                err = error.ConnectionLost()
            elif events & pyuv.UV_WRITABLE:
                err = log.callWithLogger(writer, writer.doWrite)
            if err is None and poll_error is not None:
                err = error.ConnectionLost()
            if err is not None:
                self.removeWriter(writer)
                writer.writeConnectionLost(failure.Failure(err))

    # IReactorFDSet

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read."""
        if reader in self._readers:
            # Don't add the reader if it's already there
            return
        fd = reader.fileno()
        self._readers[reader] = fd
        if fd in self._fds:
            _, writer = self._fds[fd]
            self._fds[fd] = (reader, writer)
            if writer:
                # We already registered this fd for write events,
                # update it for read events as well.
                poll_handle = self._poll_handles[fd]
                poll_handle.start(pyuv.UV_READABLE | pyuv.UV_WRITABLE, self._invoke_callback)
        else:
            self._fds[fd] = (reader, None)
            poll_handle = pyuv.Poll(self._loop, fd)
            poll_handle.start(pyuv.UV_READABLE, self._invoke_callback)
            poll_handle.fd = fd
            self._poll_handles[fd] = poll_handle

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write."""
        if writer in self._writers:
            return
        fd = writer.fileno()
        self._writers[writer] = fd
        if fd in self._fds:
            reader, _ = self._fds[fd]
            self._fds[fd] = (reader, writer)
            if reader:
                # We already registered this fd for read events,
                # update it for write events as well.
                poll_handle = self._poll_handles[fd]
                poll_handle.start(pyuv.UV_READABLE | pyuv.UV_WRITABLE, self._invoke_callback)
        else:
            self._fds[fd] = (None, writer)
            poll_handle = pyuv.Poll(self._loop, fd)
            poll_handle.start(pyuv.UV_WRITABLE, self._invoke_callback)
            poll_handle.fd = fd
            self._poll_handles[fd] = poll_handle

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read."""
        if reader in self._readers:
            fd = self._readers.pop(reader)
            _, writer = self._fds[fd]
            if writer:
                # We have a writer so we need to update the IOLoop for
                # write events only.
                self._fds[fd] = (None, writer)
                poll_handle = self._poll_handles[fd]
                poll_handle.start(pyuv.UV_WRITABLE, self._invoke_callback)
            else:
                # Since we have no writer registered, we remove the
                # entry from _fds and unregister the handler from the
                # IOLoop
                del self._fds[fd]
                del self._poll_handles[fd]

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write."""
        if writer in self._writers:
            fd = self._writers.pop(writer)
            reader, _ = self._fds[fd]
            if reader:
                # We have a reader so we need to update the IOLoop for
                # read events only.
                self._fds[fd] = (reader, None)
                poll_handle = self._poll_handles[fd]
                poll_handle.start(pyuv.UV_READABLE, self._invoke_callback)
            else:
                # Since we have no reader registered, we remove the
                # entry from the _fds and unregister the handler from
                # the IOLoop.
                del self._fds[fd]
                del self._poll_handles[fd]

    def removeAll(self):
        return self._removeAll(self._readers, self._writers)

    def getReaders(self):
        return self._readers.keys()

    def getWriters(self):
        return self._writers.keys()

    def stop(self):
        self._async_handle.close()
        for handle in self._get_loop_handles():
            if hasattr(handle, 'stop') and callable(handle.stop):
                handle.stop()
        PosixReactorBase.stop(self)

    def crash(self):
        # No need to stop handles, it's done by stop
        PosixReactorBase.crash(self)

    def runUntilCurrent(self):
        raise NotImplementedError("runUntilCurrent")

    def startRunning(self, installSignalHandlers=True):
        self._signal_watcher.start()
        _SignalReactorMixin.startRunning(self, installSignalHandlers)

    def doIteration(self, delay):
        raise NotImplementedError("doIteration")

    def mainLoop(self):
        while self._started:
            try:
                while self._started:
                    if self._stopped:
                        self.fireSystemEvent("shutdown")
                        break
                    self._loop.run()
            except:
                log.msg("Unexpected error in main loop.")
                log.err()
            else:
                for handle in self._get_loop_handles():
                    handle.close()
                # Run the loop so the close callbacks are fired and memory is freed
                # It will not block because all handles are closed
                self._loop.run()
                log.msg('Main loop terminated.')


def install():
    reactor = UVReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)

