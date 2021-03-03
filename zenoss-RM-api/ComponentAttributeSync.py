import json
import re
import sys
from pprint import pformat
import zenApiLib
from zapiScriptFunctions import getDefaultScriptArgParser, initScriptEnv


filterPattern = None
sourceObject = None
destinObject = None
counters = {}


def buildArgs():
    parser = getDefaultScriptArgParser()
    # Change default logging value. Logging arg is position 1
    parser._actions[1].default = 20
    #
    parser.description = 'Component attribute sync'
    parser.add_argument('-s', dest='sourceZ', action='store', required=True,
                        help='Zenoss instance credential section to be used as the source or if '
                            'starts with "file:" the file to use for Object Uid & attribute '
                             'values')
    parser.add_argument('-d', dest='destinationZ', action='store', required=True,
                        help='Zenoss instance credential section to be used as the destination or '
                             'if starts with "file:" the file to use to dump Object Uids & '
                             'attribute values')
    parser.add_argument('-t', dest='metaTypes', action='append', required=True,
                        help='Object type to search for. Can be defined multiple times')
    parser.add_argument('-a', dest='attributes', action='append', required=True,
                        help='Object attributes to compare & update. Can be defined multiple times')
    parser.add_argument('-x', dest='dryRun', action='store_true', required=False,
                        help='Do not make change on Destination')
    parser.add_argument('-f', dest='filterUid', action='store', required=False, default='',
                        help='Filter to use on Zenoss object uid')
    parser.add_argument('-ss', dest='sourceStart', action='store', required=False, default=0,
                        type=int, help='From source, start at')
    parser.add_argument('-se', dest='sourceEnd', action='store', required=False, default=0,
                        type=int, help='From source, end at')
    return parser.parse_args()


def _initIOObject(argValue, name):
    global sourceObject
    if 'file:' in argValue:
        filename = argValue.split(':')[1]
        if name == "Source":
            log.warn('"-t" command parameter does not apply when source is a file')
            ioObject = json.load(open(filename, 'r'))
            count('Total objects in "{}" Source file'.format(filename), len(ioObject))
            if args['sourceStart'] or args['sourceEnd']:
                ioObject = _batchWindowSlice(ioObject, args['sourceStart'], args['sourceEnd'])
        elif name == "Destination":
            ioObject = open(filename, 'w')
    else:
        try:
            ioObject = zenApiLib.zenConnector(section=argValue)
        except Exception as e:
            log.error('Issue communicating with %s Instance API\n%r', name, e)
            sys.exit(1)
    return ioObject


def _batchWindowSlice(object, start, end):
    if end != 0:
        object = object[:end]
        count('"Batch" window end at object', end)
    if start != 0:
        object = object[start:]
        count('"Batch" window start at object', start)
    count('"Batch" window Total objects', len(object))
    return object


def _searchrouterGetResults(oAPI, metaTypes):
    oAPI.setRouter('SearchRouter')
    searchResults = []
    for apiResponse in oAPI.pagingMethodCall('getAllResults', query='*', category=metaTypes):
        if not apiResponse['result'].get('total'):
            raise Exception('search_router getAllResults method call non-successful: %r', apiResponse)
        else:
            # extract uid (some reason it is keyed 'url') from search results
            searchResults.extend([x['url'] for x in apiResponse['result']['results']])
    count('API Searched "{}" objects found on Source'.format(metaTypes), len(searchResults))
    if args['sourceStart'] or args['sourceEnd']:
        searchResults = _batchWindowSlice(searchResults, args['sourceStart'], args['sourceEnd'])
    return searchResults


def _devrouterUidAttrValues(oAPI, uid, attrNames):
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
        result = apiResponse['result']['data']
        return result


def _devrouterUidSetInfo(oAPI, uid, data):
    oAPI.setRouter('DeviceRouter')
    data['uid'] = uid
    apiResponse = oAPI.callMethod('setInfo', **data)
    if not apiResponse['result']['success']:
        log.error('device_router setInfo method call non-successful: %r', apiResponse)


def _devrouterLockComponents(oAPI, uid, lockData):
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


def _uidDeviceIdAllLowerCase(uid):
    m = re.match("(.*/devices)/([a-zA-Z0-9-_.]+)/(.*)", uid)
    if m:
        return "{}/{}/{}".format(m.group(1), m.group(2).lower(), m.group(3))
    return None


def iterGetSourceX():
    # If Source is API, return Source UID
    # If Source is file, return source Values
    if args['filterUid']:
        filterPattern = re.compile(args['filterUid'])
    if isinstance(sourceObject, list):
        for sourceValues in sourceObject:
            uid = sourceValues['uid']
            if args['filterUid'] and not filterPattern.match(uid):
                count('Source objects excluded by filter')
                continue
            yield sourceValues
    else:
        for uid in _searchrouterGetResults(sourceObject, args['metaTypes']):
            if args['filterUid'] and not filterPattern.match(uid):
                count('Source objects excluded by filter')
                continue
            yield uid


def getDestinUidValues(uid):
    global destinObject, log
    if isinstance(destinObject, file):
        return True
    # return _devrouterUidAttrValues(destinObject, uid, args['attributes'])
    # Specific use-case, where destin deviceIDs became lowercase....
    destinValues = _devrouterUidAttrValues(destinObject, uid, args['attributes'])
    if destinValues is None:
        # Try UID again, but with lowercase deviceID UID
        destinUid = _uidDeviceIdAllLowerCase(uid)
        if destinUid:
            destinValues = _devrouterUidAttrValues(destinObject, destinUid, args['attributes'])
        if destinValues is None:
            log.debug('Does not exist on destination instances: "%s"', uid)
    return destinValues


def getSourceUidValues(uid):
    global destinObject, log
    # Should never get called when Source is a file
    return _devrouterUidAttrValues(sourceObject, uid, args['attributes'])


def writeSourceToFile():
    sourceData = []
    for uid in iterGetSourceX():
        sourceData.append(getSourceUidValues(uid))
    json.dump(sourceData, destinObject, indent=1)
    destinObject.close()
    count('Written to file {}'.format(args['destinationZ']), len(sourceData))


def compareAndSync():
    for data in iterGetSourceX():
        if isinstance(data, str):
            uid = data
        elif isinstance(data, dict):
            uid = data['uid']
        destinValues = getDestinUidValues(uid)
        if destinValues is None:
            count('Source objects that did not exist on Destination')
            log.debug('Does not exist on destination instances: "%s"', uid)
            continue
        if isinstance(data, str):
            sourceValues = getSourceUidValues(uid)
        elif isinstance(data, dict):
            sourceValues = data
        if sourceValues is None:
            # Should not happen, but it did once...
            log.error('Does not exist on source instance: "%s". This should not happen and implies '
                      'something is not right.', uid)
            continue
        # Sometimes the UID will be different between source/destin, see getDestinUidValues()
        # Also, should get the 'uid' attribute out of the Values dicts
        sourceUID = sourceValues.pop('uid')
        destinUID = destinValues.pop('uid')

        if sourceValues == destinValues:
            log.debug('Values match."%s"', uid)
            count('Destination objects matching Source(no change made)')
        else:
            log.info('Object synced: "%s"', destinUID)
            log.debug('%s SOURCE:%r -- DESTIN:%r', destinUID, sourceValues, destinValues)
            if args['dryRun'] is False:
                # Update Special Attributes
                if 'locking' in sourceValues:
                    _devrouterLockComponents(destinObject, destinUID, sourceValues['locking'].copy())
                    del sourceValues['locking']
                # Update General Attributes
                _devrouterUidSetInfo(destinObject, destinUID, sourceValues)
            count('Destination objects updated')


def count(name, value=None):
    if name not in counters:
        counters[name] = value if value else 1
    else:
        counters[name] += value if value else 1


if __name__ == '__main__':
    args = vars(buildArgs())
    log, rOut = initScriptEnv(args)
    log.info('Start')

    if args['dryRun']:
        log.info('DRY RUN updates will not be made to Destination, output forced into debug')
        log.setLevel(10)

    sourceObject = _initIOObject(args['sourceZ'], 'Source')
    destinObject = _initIOObject(args['destinationZ'], 'Destination')

    if isinstance(destinObject, file):
        writeSourceToFile()
    else:
        compareAndSync()

    log.info('Summary:\n' + pformat(counters, indent=1))
