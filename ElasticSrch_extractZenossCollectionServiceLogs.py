
#!/usr/bin/env python
#from zenApiLib import TitleParser
import argparse
import sys
import logging
from pprint import pformat
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from requests.packages.urllib3.util.retry import Retry
from httplib import HTTPConnection
from requests.adapters import HTTPAdapter
import requests
import json
from subprocess import Popen, PIPE

def buildArgs():
    parser = argparse.ArgumentParser(description='extract Zenoss Collection '
                        'Service logs from ElasticSearch', usage='')
    parser.add_argument('-v', dest='loglevel', action='store', type=int,
                        default=30, help='Set script logging level (DEBUG=10,'
                        ' INFO=20, WARN=30, *ERROR=40, CRTITICAL=50')
    parser.add_argument('-o', dest='outFileName', action='store', default=None,
                        help="Output to file instead of stdout.")
    parser.add_argument('-d', dest='dateString', action='store', default='10 min ago',
                        help="Extract logs from date to present. Default value: '10 min ago'")
    parser.add_argument('-q', dest='Query', action='store', default='',
                        help="Query string used in Kibana")

    return parser.parse_args()

class ElasticSrchConnector(object):
    def __init__(self, loglevel=40):
        self._url = 'http://127.0.0.1:9100/logstash-*/_search?scroll=1m'
        self.log = logging.getLogger('zenApiLib.ZenConnector')
        self.log.setLevel(loglevel)
        self.config = {
            'timeout': 30,
            'retries': 4,
        }
        self.requestSession = self.getRequestSession()
        self.payload = {}

    def getRequestSession(self):
        '''
        Setup defaults for using the requests library
        '''
        self.log.info('getRequestSession;')
        s = requests.Session()
        retries = Retry(total=self.config['retries'],
                backoff_factor=1,
                status_forcelist=[ 500, 502, 503, 504, 405 ])
        s.mount(
            'https://',
            HTTPAdapter(max_retries=retries)
        )
        s.mount(
            'http://',
            HTTPAdapter(max_retries=retries)
        )
        return s

    def callApi(self, payload):
        if self.log.getEffectiveLevel() == 10:
            HTTPConnection.debuglevel = 1
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(self.log.getEffectiveLevel())
        requests_log.propagate = True
        try:
            r = self.requestSession.post(self._url,
                verify=False,
                timeout=self.config['timeout'],
                headers={'content-type':'application/json', 'kbn-xsrf': 'true'},
                data=payload,
            )
        except Exception as e:
            msg = 'Reqests exception: %s' % e
            self.log.error(msg)
        else:
            return self._validateRawResponse(r)

    def scroll(self, payload):
        scrollResults = self.callApi(payload)
        if '_scroll_id' in scrollResults:
            self._url = 'http://127.0.0.1:9100/_search/scroll'
            scrollPayload = {
                'scroll': '1m',
                'scroll_id': scrollResults['_scroll_id']
            }
        apiResultsReturned = len(scrollResults['hits']['hits'])
        apiResultsTotal = scrollResults['hits']['total']

        yield scrollResults

        while (apiResultsReturned < apiResultsTotal):
            scrollResults = self.callApi(json.dumps(scrollPayload))
            apiResultsReturned += len(scrollResults['hits']['hits'])
            yield scrollResults

        r = self.requestSession.delete(self._url,
            verify=False,
            timeout=self.config['timeout'],
            headers={'content-type':'application/json', 'kbn-xsrf': 'true'},
            data=json.dumps(scrollPayload),
        )

    def _validateRawResponse(self, r):
        '''
        todo
        '''
        self.log.info("_validateRawResponse: passed object type of '%s'" % type(r))
        rJson = {}
        if r.status_code != 200:
            self.log.error("API call returned a '%s' http status." % r.status_code)
            self.log.debug("API EndPoint response: %s\n%s ", r.reason, r.text)
        else:
            if 'Content-Type' in r.headers:
                if 'application/json' in r.headers['Content-Type']:
                    rJson = r.json()
                    self.log.debug('_validateRawResponse: Response returned:\n%s' % rJson)
                elif 'text/html' in r.headers['Content-Type']:
                    parser = TitleParser()
                    parser.feed(r.text)
                    msg = "HTML response from API call. HTML page title: '%s'" % parser.title
                    self.log.error(msg)
                    self.log.debug("API EndPoint response: %s\n%s ", r.reason, r.text)
                    rJson = {}
                else:
                    msg = "Unknown 'Content-Type' response header returned: '%s'" % r.headers['Content-Type']
                    self.log.error(msg)
                    self.log.debug("API EndPoint response: %s\n%s ", r.reason, r.text)
                    rJson = {}
            else:
                msg = "Missing 'Content-Type' in API response's header"
                self.log.error(msg)
                self.log.debug("API EndPoint response: %s\n%s ", r.reason, r.text)
                rJson = {}
        return rJson

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    logging.getLogger().setLevel(logging.ERROR)
    args = vars(buildArgs())
    log = logging.getLogger(__file__)
    log.setLevel(args['loglevel'])
    if args['outFileName']:
        rOut = open(args['outFileName'], 'w')
    else:
        rOut = sys.stdout
    api = ElasticSrchConnector(
        loglevel=args['loglevel']
    )
    p = Popen('date +%s -d "{}"'.format(args['dateString']), stdout=PIPE, stderr=PIPE, shell=True)
    output, err = p.communicate()
    filterDate = "{}000".format(output.strip())
    esQuery = {
        "size":1000,
        "query": {
        "filtered": {
            "query": {
                "query_string": {
                    "query": args['Query'],
                    "analyze_wildcard": True
                }
            },
            "filter": {
                "bool": {
                    "must": [{
                        "range": {
                            "@timestamp": {
                                "gte": filterDate,

                            }
                        }
                    }]
                }
            }
        }},
        "sort":[{
            "@timestamp":{
                "order":"asc",
                "unmapped_type":"boolean"
            }
        }]
    }
    if args['loglevel'] > 30:
        print >>sys.stderr, "query:{}".format(pformat(esQuery))
    for esResults in api.scroll(json.dumps(esQuery)):
        if args['loglevel'] > 30:
            print >>sys.stderr, "results:{}, total:{}".format(
                len(esResults['hits']['hits']),
                esResults['hits']['total']
            )
        for esLog in esResults['hits']['hits']:
            esMsg = esLog['_source']['message']
            if isinstance(esMsg, (list, tuple)):
                esMsg = esMsg[0]
            print >>rOut, "{}/{}::'{}'".format(
                esLog['_source']['fields']['servicepath'],
                esLog['_source']['fields']['instance'],
                esMsg
            )
