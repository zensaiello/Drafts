import re
import sys
import zenApiLib
from zapiScriptFunctions import getDefaultScriptArgParser, initScriptEnv


def buildArgs():
    parser = getDefaultScriptArgParser()
    # Change default logging value. Logging arg is position 1
    parser._actions[1].default = 20
    #
    parser.description = 'Component attribute sync'
    parser.add_argument('-s', dest='sourceZ', action='store', required=True,
                        help='Zenoss instance credential section to be used as the source')
    parser.add_argument('-d', dest='destinationZ', action='store', required=True,
                        help='Zenoss instance credential section to be used as the destination')
    parser.add_argument('-t', dest='metaTypes', action='append', required=True,
                        help='Object type to search for. Can be defined multiple times')
    parser.add_argument('-a', dest='attributes', action='append', required=True,
                        help='Object attributes to compare & update. Can be defined multiple times')
    parser.add_argument('-x', dest='dryRun', action='store_true', required=False,
                        help='Do not make change on Destination')
    parser.add_argument('-f', dest='filterUid', action='store', required=False, default='',
                        help='Filter to use on Zenoss object uid')
    return parser.parse_args()


def searchrouterGetResults(oAPI, metaTypes):
    oAPI.setRouter('SearchRouter')
    searchResults = []
    for apiResponse in oAPI.pagingMethodCall('getAllResults', query='*', category=metaTypes):
        if not apiResponse['result'].get('total'):
            raise Exception('search_router getAllResults method call non-successful: %r', apiResponse)
        else:
            # extract uid (some reason it is keyed 'url') from search results
            searchResults.extend( [x['url'] for x in apiResponse['result']['results']])
    return searchResults


def devrouterUidAttrValues(oAPI, uid, attrNames):
    oAPI.setRouter('DeviceRouter')
    apiResponse = oAPI.callMethod(
        'getInfo',
        uid=uid,
        keys=attrNames
    )
    if not apiResponse['result']['success']:
        if 'ObjectNotFoundException' in apiResponse['result']['msg']:
            return None
        log.error('device_router getInfo method call non-successful: %r', apiResponse)
    else:
        return apiResponse['result']['data']


def devrouterUidAttrExist(oAPI, uid, attrNames):
    apiData = devrouterUidAttrValues(oAPI, uid, attrNames)
    return all(attrName in apiData for attrName in attrNames)


def devrouterUidSetInfo(oAPI, data):
    oAPI.setRouter('DeviceRouter')
    # uid info is defined in data
    apiResponse = oAPI.callMethod('setInfo', **data)
    if not apiResponse['result']['success']:
        log.error('device_router setInfo method call non-successful: %r', apiResponse)


def devrouterLockComponents(oAPI, uid, lockData):
    oAPI.setRouter('DeviceRouter')
    # Massage data from getInfo() into format lockComponents() takes
    lockData['uids'] = [uid]
    lockData['sendEvent'] = lockData['events']
    del lockData['events']
    # hashcheck is needed, otherwise: "TypeError: lockComponents() takes at least 3 arguments"
    lockData['hashcheck'] = None
    apiResponse = oAPI.callMethod(
        'lockComponents',
        **lockData
    )
    if not apiResponse['result']['success']:
        log.error('device_router lockComponents method call non-successful: %r', apiResponse)


if __name__ == '__main__':
    args = vars(buildArgs())
    log, rOut = initScriptEnv(args)

    if args['dryRun']:
        log.info('DRY RUN updates will not be made to Destination, output forced into debug')
        log.setLevel(10)

    syncChangeCount = 0
    notOnDestin = 0

    try:
        sourceAPI = zenApiLib.zenConnector(section=args['sourceZ'])
    except Exception as e:
        log.error('Issue communicating with Source Instance API\n%r', e)
        sys.exit(1)
    try:
        destinAPI = zenApiLib.zenConnector(section=args['destinationZ'])
    except Exception as e:
        log.error('Issue communicating with Destination Instance API\n%r', e)
        sys.exit(1)

    sourceUids = searchrouterGetResults(sourceAPI, args['metaTypes'])
    # Check for results
    if not sourceUids:
        log.error("No %s objects found on source", args['metaTypes'])
        sys.exit(1)

    totalSourceUids = len(sourceUids)
    filteredSourceUids = 0
    if args['filterUid']:
        filterPattern = re.compile(args['filterUid'])
        sourceUidsFiltered = [uid for uid in sourceUids if filterPattern.match(uid)]
        filteredSourceUids = len(sourceUidsFiltered)
        if totalSourceUids == filteredSourceUids:
            log.error('Your filter of "%s" did not exclude any uids, total objects %s',
                      args['filterUid'],
                      totalSourceUids)
    else:
        sourceUidsFiltered = sourceUids
    for uid in sourceUidsFiltered:
        destinValues = devrouterUidAttrValues(destinAPI, uid, args['attributes'])
        if destinValues is None:
            log.debug('Does not exist on destination instances: "%s"', uid)
            notOnDestin += 1
            continue
        sourceValues = devrouterUidAttrValues(sourceAPI, uid, args['attributes'])
        if sourceValues != destinValues:
            log.info('Object synced: "%s"', uid)
            log.debug('\nSOURCE:%r\nDESTIN:%r', sourceValues, destinValues)
            if args['dryRun'] is False:
                # Update Special Attributes
                if 'locking' in sourceValues:
                    devrouterLockComponents(destinAPI, uid, sourceValues['locking'].copy())
                    del sourceValues['locking']
                # Update General Attributes
                devrouterUidSetInfo(destinAPI, sourceValues)
            syncChangeCount += 1

    log.info('Summary:\n%s objects modified on Destination\n%s objects excluded by "%s" filter\n'
             '%s Total Source objects found\n%s objects not found on Destination',
             syncChangeCount,
             totalSourceUids - filteredSourceUids,
             args['filterUid'],
             totalSourceUids,
             notOnDestin)
