
import twisted_pyuv
twisted_pyuv.install()

from twisted.internet import reactor
from twisted.internet.protocol import Factory, Protocol


class EchoProtocol(Protocol):
    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        self.factory.numProtocols += 1
        self.transport.write("Welcome! There are currently %d open connections.\n" % (self.factory.numProtocols,))

    def connectionLost(self, reason):
        self.factory.numProtocols -= 1

    def dataReceived(self, data):
        self.transport.write(data)

class EchoFactory(Factory):
    def __init__(self):
        self.numProtocols = 0

    def buildProtocol(self, addr):
        return EchoProtocol(self)


reactor.listenTCP(8889, EchoFactory())
reactor.run()

