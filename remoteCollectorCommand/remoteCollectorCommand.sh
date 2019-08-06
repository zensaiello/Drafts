#!/bin/bash

# Warning - POC quality - NOT READY FOR PRODUCTION
# Example script to get data from a script, add the data to an event, have that data get into a SNOW incident.

# First step is to get the data from the switch.
# Initial requirements have us running 3 commands
# SH SYSTEM, SH INT, and SH LOG

# What info will we get

# switch ip
IP=$1

# evid
EVID=$2

# failureName
FAILURENAME=${3//[$'\t\r\n ']}

cd /var/zenoss
export USER=''
export SSHPASS=''
export SSHKEY=''
ZENOSS_URL="https://zenny123.zenoss.io/cz0"
APIKEY="Zenny123"


# Generic call to make Zenoss JSON API calls easier on the shell.
zenoss_api () {
    ROUTER_ENDPOINT=$1
    ROUTER_ACTION=$2
    ROUTER_METHOD=$3
    DATA=$4

   if [ -z "${DATA}" ]; then
       echo "Usage: zenoss_api <endpoint> <action> <method> <data>"
       return 1
   fi

   #Debug
   #echo "{\"action\":\"$ROUTER_ACTION\",\"method\":\"$ROUTER_METHOD\",\"data\":[$DATA], \"tid\":1}" 1>&2
   retry=1
   until [ $retry -ge 3 ] ; do
       curl \
           -m 5 -s \
           -X POST \
           -H "Content-Type: application/json" \
           -H "z-api-key: $APIKEY" \
           -d "{\"action\":\"$ROUTER_ACTION\",\"method\":\"$ROUTER_METHOD\",\"data\":[$DATA], \"tid\":1}" \
           "$ZENOSS_URL/zport/dmd/$ROUTER_ENDPOINT" && break
       ((retry++))
       echo "API call failed, retry $retry" >&2
       sleep 3
   done
}

zenoss_add_log_event() {
    zenoss_api evconsole_router EventsRouter write_log "{\"evid\":\"$EVID\",\"message\":$UPDATEDATA}" &>/dev/null

}

zenoss_get_uid_from_ip() {
    zenoss_api id_router IdentificationRouter resolve "{\"id\":{\"searchTerm\":\"$IP\"},\"idScheme\":\"search\",\"allowMultiple\": true}" | jq -ar '.result.uids[0]'
}

zenoss_get_commands_from_uid() {
    zenoss_api properties_router PropertiesRouter getZenProperty "{\"uid\":\"$DEVICE_UID\",\"zProperty\":\"$FAILURENAME\"}" | jq -ar '.result.data.valueAsString'
}

zenoss_set_ssh_cred() {
    export USER=`zenoss_api properties_router PropertiesRouter getZenProperty "{\"uid\":\"$DEVICE_UID\",\"zProperty\":\"zCommandUsername\"}" | jq -ar '.result.data.valueAsString'`
    #export SSHPASS=`zenoss_api properties_router PropertiesRouter getZenProperty "{\"uid\":\"$DEVICE_UID\",\"zProperty\":\"zCommandPassword\"}" | jq -ar '.result.data.valueAsString'`
    export SSHPASS='Zenny123'
    export SSHKEY=`zenoss_api properties_router PropertiesRouter getZenProperty "{\"uid\":\"$DEVICE_UID\",\"zProperty\":\"zKeyPath\"}" | jq -ar '.result.data.valueAsString'`
}

zenoss_send_infoError() {
    zenoss_api evconsole_router EventsRouter add_event "{\"device\":\"$IP\",\"summary\":\"$FAILURENAME CLI error\", \"component\":\"\", \"severity\":2, \"evclasskey\":\"\", \"evclass\":\"\/App\/Zenoss\", \"message\":\"$1\"}" &>/dev/null
}


DEVICE_UID=`zenoss_get_uid_from_ip`

if [ -z "$DEVICE_UID" ] ; then
   exit 1
fi
mapfile -t COMMANDS < <(zenoss_get_commands_from_uid)
zenoss_set_ssh_cred

if [[ -z "$SSHPASS" || $SSHPASS == "null" ]] ; then
    BASECOMMAND="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $SSHKEY $USER@$IP"
else
    BASECOMMAND="/var/zenoss/sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 $USER@$IP"
fi

# Get the data
for i in "${!COMMANDS[@]}"; do
  #printf "%s\t%s\n" "$i" "${COMMANDS[$i]}"
  rOut=$(exec $BASECOMMAND ${COMMANDS[$i]} 1>$EVID-$i.out 2>$EVID-$i.err)
  rCode=$?
  if [ $rCode -ne 0 ] ; then
     rError=`cat $EVID-$i.err`
     rError=${rError//[$'\t\r\n']}
     if [ $rCode -eq 5 ] ; then
        rError="Invalid/incorrect password"
     fi
     echo "$rError"
     rm -f "$EVID-$i.err"
     zenoss_send_infoError "exitCode: $rCode. $rError"
     exit 2
  fi
done

# We have data in a file, now lets update our event

for i in "${!COMMANDS[@]}"; do
    UPDATEDATA=`cat $EVID-$i.out| jq -aR --slurp .`
    zenoss_add_log_event  "$EVID" "${UPDATEDATA}" || exit 2
    rm -f $EVID-$i.out $EVID-$i.err
done

# This should be it
# Clean up

exit 0
