#!/bin/bash
# see https://docs.docker.com/engine/reference/builder/#entrypoint
# and https://success.docker.com/article/use-a-script-to-initialize-stateful-container-data
set -e

if [ "$1" = '/bin/bash' ]; then
    # Ensure the database has been initialized,
    # with a sleep to ensure the container is ready.
    sleep 10 && poetry run flask create-tables

    # Optionally start cron
    if [ "$START_CRON" = 'true' ]; then
        echo "Starting cron."
        service cron start
    else
        echo "Not starting cron."
    fi

    # Optionally spin up xvfb in the background
    if [ ! -z "$DISPLAY" ]; then
        # Clean up from previous runs, if necessary
        rm -f /tmp/.X99-lock
        echo "Starting Xvfb on $DISPLAY"
        Xvfb $DISPLAY &
    else
        echo "Not starting Xvfb."
    fi

    # Optionally spin up the Flask development server
    if [ "$START_FLASK_SERVER" = 'true' ]; then
        poetry run flask run --host=0.0.0.0 &
    else
        echo "Not starting Flask development server."
    fi

    # Optionally create an access key
    if [ ! -z "$CREATE_ACCESS_KEY_WITH_LABEL" ]; then
        KEY_MESSAGE=`poetry run flask create-access-key --label $CREATE_ACCESS_KEY_WITH_LABEL`
        echo $KEY_MESSAGE
        echo "Saving access key to 'docker/access_keys/access_key.txt'"
        echo $KEY_MESSAGE >> docker/access_keys/access_key.txt
    fi

    # Optionally spin up a Celery worker
    if [ "$START_CELERY" = 'true' ]; then
        echo "Launching Celery."
        poetry run celery -A make_celery worker --loglevel=info --concurrency=3 --without-gossip --without-mingle --without-heartbeat -B -Q main,background -n w1@%h &
    else
        echo "Not launching Celery."
    fi
fi
exec "$@"
