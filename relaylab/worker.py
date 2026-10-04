"""Run with python -m relaylab.worker. Use exactly one worker process."""
import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import store


class NoRedirects(HTTPRedirectHandler):
    # A redirect is a delivery failure, not permission to send data elsewhere.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def deliver_next(db, receiver_url, timeout=3):
    event = store.next_pending(db)
    if event is None:
        return False
    request = Request(receiver_url, data=json.dumps(event).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "X-RelayLab-Event-ID": event["id"]}, method="POST")
    status, error = None, None
    try:
        with build_opener(NoRedirects()).open(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        status, error = exc.code, f"Receiver returned HTTP {exc.code}"
        exc.close()
    except (URLError, TimeoutError, OSError) as exc:
        error = str(exc)[:500]
    store.record_attempt(db, event["id"], status, error)
    logging.info("event=%s status=%s error=%s", event["id"], status, error)
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    receiver = os.getenv("RELAYLAB_RECEIVER_URL", "http://127.0.0.1:8001/webhook")
    store.initialize()
    logging.info("Single worker started; receiver=%s", receiver)
    try:
        while True:
            if not deliver_next(store.DEFAULT_DB, receiver):
                time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info("Worker stopped")


if __name__ == "__main__":
    main()
