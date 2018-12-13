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
  -h, --help      show this help message and exit
  -v LOGLEVEL     Set script logging level (DEBUG=10, INFO=20, WARN=30,
                  *ERROR=40, CRTITICAL=50
  -o OUTFILENAME  Output to file instead of stdout.
  -d DATESTRING   Extract logs from date to present. Default value: '10 min
                  ago'
  -q QUERY        Query string

```

### Examples:

```
# ./ElasticSrch_extractZenossCollectionServiceLogs.py -d "1 min ago"

# ./ElasticSrch_extractZenossCollectionServiceLogs.py -d "24 hours ago" -q "fields.type:zenpython" -d "1 hour ago" -o zenpython.stats.log

# ./ElasticSrch_extractZenossCollectionServiceLogs.py -d "12 hours ago" -q "fields.type:zenmodeler AND (message:\"Starting collector\" OR message:\"Scan time\" OR message:\"scanned during collector loop\")"

# Great way to extract zenoss service stats output
# ./ElasticSrch_extractZenossCollectionServiceLogs.py -d "12 hours ago" -q 'message:"Task States Summary"'
```
