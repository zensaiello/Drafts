#!/usr/bin/env python

# stdlib Imports
import json
from sys import exit, argv
import os
from urlparse import urlparse
import logging
import zenApiLib
import re


# Global Variables
zenAPI = zenApiLib.zenConnector(section = 'default')
zenAPI.log.setLevel(logging.WARN)
zenInstance = urlparse(zenAPI.config['url']).hostname



def ServiceRouter(sMethod, dData={}):
    zenAPI.setRouter('ServiceRouter')
    respData = zenAPI.callMethod(sMethod, **dData)
    if not respData['result']['success']:
        print "ERROR: ServiceRouter %s method call non-successful" % sMethod
        print respData
        print "Data submitted was:"
        print response.request.body
        exit(1)
    if 'services' in respData['result']:
        return respData['result']['services']
    elif 'data' in respData['result']:
        return respData['result']['data']
    else:
        return None


def log2stdout(loglevel):
    '''
    Setup logging
    '''
    logging.basicConfig(
        format = '%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    logging.getLogger().setLevel(loglevel)
    return logging.getLogger('importTriggersNotifications')


if __name__ == "__main__":
    log = log2stdout(logging.INFO)
    log.info("Script started, importing to %s" % zenInstance)
    argv.pop(0)
    changeCount = 0
    for sFileName in argv:
        if not os.path.isfile(sFileName):
            print "ERROR: %s does not exist, ignoring" % sFileName
            continue
        log.debug("Reading file %s" % sFileName)
        oFile = open(sFileName, 'r')
        impSvcConfig = json.loads(oFile.read())
        oFile.close()
        z = re.match('.*/(.*)\.json', sFileName)
        # 
        svcUid = "/zport/dmd/Services/{}".format(
            z.group(1).replace('-_-', '/')
        )
        curSvcConfig = ServiceRouter(
            'getInfo',
            dData={'uid': svcUid}
        )
        # remove unNeeded attributes
        del curSvcConfig['count']
        del curSvcConfig['id']
        del curSvcConfig['meta_type']
        del curSvcConfig['inspector_type']
        if (curSvcConfig == impSvcConfig) is False:
            ServiceRouter(
                'setInfo',
                dData=impSvcConfig
            )
            log.info('%s - config differs, applying configuration', sFileName)
            changeCount += 1
    log.info("Script completed, %s configurations applied out of %s", changeCount, len(argv))
