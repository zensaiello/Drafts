#!/usr/bin/env python

# stdlib Imports
import json
from sys import exit
import os
from urlparse import urlparse
import zenApiLib

zenAPI = zenApiLib.zenConnector(section = 'default')
zenInstance = urlparse(zenAPI.config['url']).hostname


def ServiceRouter(sMethod, dData={}):
    zenAPI.setRouter('ServiceRouter')
    respData = zenAPI.callMethod(sMethod, **dData)
    if not respData['result']['success']:
        print "ERROR: ServiceRouter %s method call non-successful" % sMethod
        print respData
        exit(1)
    if 'services' in respData['result']:
        return respData['result']['services']
    elif 'data' in respData['result']:
        return respData['result']['data']
    else:
        return None
    

def export2File(svcUid):
    exportPath = './export_%s' % zenInstance
    if not os.path.exists(exportPath):
        os.makedirs(exportPath)
    # Shear off "/zport/dmd/Services/" and then replace "/" with "-"
    fileName = svcUid[20:].replace('/', '-_-')
    print "INFO: writing %s/%s.json" % (
        exportPath,
        fileName,
    )
    try:
        svcConfig = ServiceRouter(
            'getInfo',
            dData={'uid': svcUid}
        )
        exportFile = open("%s/%s.json" % (
            exportPath,
            fileName),
            'w'
        )
        # remove unNeeded attributes
        del svcConfig['count']
        del svcConfig['id']
        del svcConfig['meta_type']
        del svcConfig['inspector_type']
        exportFile.write(json.dumps(svcConfig))
        exportFile.close()
    except Exception as e:
        print "ERROR: %r" % (e)
        exit(1)

if __name__ == "__main__":
    print "Script started, exporting from %s" % zenInstance
    lIpServices = ServiceRouter(
        'query',
        dData={
			"params": {},
			"uid": "/zport/dmd/Services/IpService",
			"sort": "name",
			"dir": "ASC"
        })
    print "INFO: got IP Service configurations, total of %s" % (
        str(len(lIpServices))
    )
    for svcSummary in lIpServices:
        export2File(svcSummary['uid'])
    print "Script completed"
