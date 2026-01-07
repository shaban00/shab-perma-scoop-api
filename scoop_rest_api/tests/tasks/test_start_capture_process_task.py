"""
Test suite for the "start-capture-process" celery task.
"""


def test_start_capture_process_task(celery_worker, access_key, id_capture):
    """
    Takes a single job off the queue and processes it.
    Asserts that the Celery task succeeded... not that the capture succeeded.
    """
    from scoop_rest_api.models import Capture
    from scoop_rest_api.tasks import start_capture_process

    capture_before_run = Capture.get(Capture.id_capture == id_capture)
    capture_after_run = None

    # Process pending capture
    job = start_capture_process.delay()
    job.wait(60)
    assert job.status == "SUCCESS"

    capture_after_run = Capture.get(Capture.id_capture == id_capture)

    assert capture_before_run.id_capture == capture_after_run.id_capture
    assert capture_before_run.status != capture_after_run.status
    assert capture_before_run.ended_timestamp != capture_after_run.ended_timestamp
