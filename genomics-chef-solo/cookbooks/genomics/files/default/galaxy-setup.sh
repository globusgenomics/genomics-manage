#!/bin/sh

cd `dirname $0`

# If there is a .venv/ directory, assume it contains a virtualenv that we
# should run this instance in.
if [ -d .venv ];
then
    printf "Activating virtualenv at %s/.venv\n" $(pwd)
    . .venv/bin/activate
fi

# If there is a file that defines a shell environment specific to this
# instance of Galaxy, source the file.
if [ -z "$GALAXY_LOCAL_ENV_FILE" ];
then
    GALAXY_LOCAL_ENV_FILE='./config/local_env.sh'
fi

if [ -f $GALAXY_LOCAL_ENV_FILE ];
then
    . $GALAXY_LOCAL_ENV_FILE
fi

python ./scripts/check_python.py
[ $? -ne 0 ] && exit 1

./scripts/common_startup.sh