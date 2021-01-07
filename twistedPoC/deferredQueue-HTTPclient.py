from twisted.internet import reactor, defer
from twisted.internet.task import deferLater

from twisted.web.client import Agent
from twisted.web.http_headers import Headers

import Products.ZenUtils.Map as Map

import Globals
import logging
import sys
from os import environ
import time
# generate random integer values
from random import seed
from random import randint
# seed random number generator
seed(1)

_repRate = Map.Timed({}, 1)
rateLimit = 10      # 10 per timeout specified in Map.Timed() above
agent = Agent(reactor)

if 'DEBUGUT' in environ:
    zlog = logging.getLogger("zen")
    zlog.setLevel(10)
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream_handler.setFormatter(formatter)
    zlog.addHandler(stream_handler)


class eDeferredQueue(defer.DeferredQueue):

    def get(self):
        if self.pending:
            return self.pending.pop(0)
        elif self.backlog is None or len(self.waiting) < self.backlog:
            d = defer.Deferred(canceller=self._cancelGet)
            self.waiting.append(d)
            return d
        else:
            raise defer.QueueUnderflow()


def onResponse(response, responseTimeouter, startTime):
    print("response {!r}".format(response))
    if responseTimeouter.active():
        responseTimeouter.cancel()
    setattr(response, 'timeTaken', ((time.time() * 1000) - (startTime * 1000)))

    return response


def show(data):
    # print "result are {!r}".format(data)
    return data


def makeReq(url):
    _repRate[time.time()] = url
    print " -Requesting"
    d = agent.request(
        b'GET',
        url,
        Headers({'User-Agent': ['Twisted Web Client Example']}),
        None)
    return d


def checkQueue(urlRequests):
    print("Checking out queue. Rate {}/{}s [{}/{} pending/waiting]".format(
        len(_repRate),
        _repRate.timeout,
        len(urlRequests.pending),
        len(urlRequests.waiting)
    ))
    _repRate.clean()
    try:
        while urlRequests.pending:
            if len(_repRate) < rateLimit:
                urlRequest = urlRequests.get()
                urlRequest.addCallback(makeReq)
                urlRequest.addCallback(show)
            else:
                print " -RateLimit met {}/{}s".format(len(_repRate), _repRate.timeout)
                break
        else:
            # reactor.stop()
            # print "Nothing to process"
            pass
    except Exception as e:
        print "Badness ! {!r}".format(e)
        import pdb; pdb.set_trace()

    deferLater(reactor, 1, checkQueue, urlRequests)


def putInReq(urlRequests):
    numReqs = xrange(randint(12, 24))
    for _ in numReqs:
        d = defer.Deferred()
        d.callback('http://10.88.111.220')
        try:
            urlRequests.put(d)
        except Exception as e:
            print "ERROR {!r}".format(e)
            break
    print "Putting {} requests into queue".format(numReqs)
    deferLater(reactor, randint(0, 3), putInReq, urlRequests)


def main():
    defer.setDebugging(True)
    urlRequests = eDeferredQueue(size=50, backlog=150)

    deferLater(reactor, randint(0, 3), putInReq, urlRequests)
    deferLater(reactor, 1, checkQueue, urlRequests)
    reactor.run()


if __name__ == '__main__':
    main()
