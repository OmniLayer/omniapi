#!/bin/bash
PYTHONBIN=python

kill_child_processes() {
  kill $SERVER_PID
  kill $WEBSOCKET_PID
  rm -f $LOCK_FILE
}

# Ctrl-C trap. Catches INT signal
trap "kill_child_processes 1 $$; exit 0" INT
echo "Starting app.sh: $(TZ='UTC' date)"

echo "Establishing environment variables..."
APPDIR=`pwd`
LOCK_FILE=$APPDIR/omniapi.lock

# Export directories for API scripts to use

echo "Beginning main run loop..."
while true
do

  # check lock (not to run multiple times)
  if [ ! -f $LOCK_FILE ]; then

    # lock
    touch $LOCK_FILE

    #Update debug level

    if [ "$1" = "-debug" ]; then
        DEBUGLEVEL=$2
    else
        DEBUGLEVEL=0
    fi
    export DEBUGLEVEL

    ps cax | grep uwsgi > /dev/null
    if [ $? -eq 0 ]; then
        echo "uwsgi api is running."
      else
        echo "Starting uwsgi daemon..."
        cd $APPDIR/api
        #if [[ "$OSTYPE" == "darwin"* ]]; then
        uwsgi -s 127.0.0.1:1088 -p 8 -M --vhost --enable-threads --logto $APPDIR/apps.log &
        #else
        #  uwsgi -s 127.0.0.1:1088 -p 8 -M --vhost --enable-threads --plugin $PYTHONBIN --logto $APPDIR/apps.log &
        #fi
        SERVER_PID=$!
        echo $SERVER_PID > /tmp/omniapi.pid
        #get snapshot of directory files
        APISHA=`ls -lR $APPDIR/api/*.py | sha1sum`
    fi

    #check if api files have changed
    CHECKSHA=`ls -lR $APPDIR/api/*.py | sha1sum`
    #Trigger api reload if changed
    if [ "$APISHA" != "$CHECKSHA" ]; then
        uwsgi --reload /tmp/omniapi.pid
        APISHA=$CHECKSHA
        echo Api Reloaded
    fi

    ps a | grep -v grep | grep "python websocket.py" > /dev/null
    if [ $? -eq 0 ]; then
        echo "websocket api is running."
      else
        echo "Starting websocket daemon..."
        cd $APPDIR/api
        $PYTHONBIN websocket.py > $APPDIR/websocket.log 2>&1 &
        WEBSOCKET_PID=$!
    fi

    # unlock
    rm -f $LOCK_FILE
  fi

  echo "Done, sleeping..."
  # Wait a minute, and do it all again.
  sleep 60
done
