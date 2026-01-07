import datetime
from pathlib import Path

from billiard import current_process
from celery import shared_task
from flask import current_app

from scoop_rest_api.models import Capture
from scoop_rest_api.utils import ScoopRunner, check_proxy_port


def get_unique_port(task):
    PROXY_PORT = int(current_app.config["PROXY_PORT"])

    worker_name = task.request.hostname
    try:
        # if worker names are of the expected format, "w1@.....",
        # extract the worker's number
        worker_number = int(worker_name.split("@")[0][1:])
    except (AttributeError, ValueError):
        # if the worker name doesn't match that format
        # (for example, if running locally with task_always_eager=True)
        # don't attempt this optimization
        worker_number = 1

    try:
        # if workers are running with any concurrency, get this
        # child's index
        worker_index = current_process().index
    except AttributeError:
        # if we don't have an index, for instance, if this task is invoked
        # with .run(), default to 0
        worker_index = 0

    return PROXY_PORT + 100 * (worker_number - 1) + worker_index


@shared_task(bind=True)
def start_capture_process(self):
    """
    Take a capture from the queue and process it.

    If interrupted during capture, puts the capture back into the queue.
    """
    proxy_port = get_unique_port(self)

    #
    # Check for presence of deployment sentinel
    #
    sentinel = Path(current_app.config["DEPLOYMENT_SENTINEL_PATH"])
    if sentinel.exists():
        current_app.logger.error("Deployment sentinel present, exiting.")
        return

    #
    # If proxy port is available, reserve next capture
    #
    proxy_port_is_available = check_proxy_port(proxy_port)
    if proxy_port_is_available is True:
        capture = Capture.get_next_capture(reserve=True)
    else:
        capture = None
        current_app.logger.warning(f"(Pre-capture) | Port {proxy_port} already in use - retrying")
        start_capture_process.delay()

    #
    # Return early if no capture to process
    #
    if capture is None:
        return

    #
    # Execute capture via Scoop
    #
    try:
        scoop_runner = ScoopRunner(capture, proxy_port)
        scoop_runner.run()
    except Exception:
        capture.status = "failed"
        capture.ended_timestamp = datetime.datetime.now(datetime.UTC)
        capture.save()
        current_app.logger.exception(f"Capture #{capture.id_capture} | Failed (other, see logs)")
    finally:
        if capture.callback_url is not None:
            capture.call_callback_url()

    #
    # Start next capture, if one is available
    #
    start_capture_process.delay()
