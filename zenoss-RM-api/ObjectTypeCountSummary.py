import sys
import zenApiLib
from zapiScriptFunctions import getDefaultScriptArgParser, initScriptEnv
from pprint import pformat


def buildArgs():
    parser = getDefaultScriptArgParser()
    # Change default logging value. Logging arg is position 1
    parser._actions[1].default = 20
    return parser.parse_args()


if __name__ == '__main__':
    args = vars(buildArgs())
    log, rOut = initScriptEnv(args)

    apiSearchRouter = zenApiLib.zenConnector(
        section=args['configSection'],
        cfgFilePath=args['configFilePath'],
        routerName='SearchRouter'
    )
    apiResponse = apiSearchRouter.callMethod('getCategoryCounts', query='*')
    if apiResponse['result'].get('total'):
        log.info(pformat(apiResponse['result']['results']))
        log.info('Total: %s', apiResponse['result']['total'])
    else:
        log.error('Issue making API call, %r', apiResponse)