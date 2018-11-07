# Drafts
Works in progress, do not use

## ElasticSrch_extractZenossCollectionServiceLogs.py
Script to extract Zenoss Collection Service logs from ElasticSearch

### Usage:

```
# ./ElasticSrch_extractZenossCollectionServiceLogs.py -h
usage:

extract Zenoss Collection Service logs from ElasticSearch

optional arguments:
  -h, --help           show this help message and exit
  -v LOGLEVEL          Set script logging level (DEBUG=10, INFO=20, WARN=30,
                       *ERROR=40, CRTITICAL=50
  -o OUTFILENAME       Output to file instead of stdout.
   -C COLLECTORNAME     Collector service is running under. Default:
                       "localhost"
  -S SERVICENAME       Service to extract logs for
  -d DATESTRING        Extract logs from date to present. Default value: '10
                       min ago'
  -f ADDITIONALFILTER  Addtional filter to collectorName & serviceName.
                       Example: '"match":{"message": "Detailed Scheduler
                       Statistics"}'
```

### Examples:

```
# ./ElasticSrch_extractZenossCollectionServiceLogs.py -S zenpython -d "1 day ago"

# ./ElasticSrch_extractZenossCollectionServiceLogs.py -S zenpython -d "1 hour ago" -f '"match":{"message": "Detailed Scheduler Statistics"}' -o zenpython.stats.log

# ./ElasticSrch_extractZenossCollectionServiceLogs.py -S zenpython -d "1 hour ago" -f '"match":{"message": "ERROR"}'
```
