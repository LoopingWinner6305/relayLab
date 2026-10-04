import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from relaylab import store
from relaylab.worker import deliver_next


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.sqlite3"
        store.initialize(self.db)
        self.receipts = []
        receipts = self.receipts

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                event = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                receipts.append(event)
                self.send_response(503 if self.path == "/fail" else 200)
                self.end_headers()
                self.wfile.write(b'{}')

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def submit(self):
        return store.accept_event(self.db, "evt-1", "sensor.reading", {"temperature_c": 28.4})

    def test_successful_delivery_records_real_http_attempt(self):
        self.submit()
        self.assertEqual(store.get_event(self.db, "evt-1")["status"], "pending")
        self.assertTrue(deliver_next(self.db, self.url + "/webhook"))
        result = store.get_event(self.db, "evt-1")
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(result["attempts"][0]["http_status"], 200)
        self.assertEqual(self.receipts[0]["payload"], {"temperature_c": 28.4})

    def test_duplicate_does_not_create_another_delivery_job(self):
        self.assertTrue(self.submit())
        self.assertFalse(self.submit())
        self.assertEqual(len(store.list_events(self.db)), 1)
        deliver_next(self.db, self.url + "/webhook")
        self.assertFalse(deliver_next(self.db, self.url + "/webhook"))
        self.assertEqual(len(self.receipts), 1)

    def test_same_id_different_payload_is_rejected(self):
        self.submit()
        with self.assertRaises(ValueError):
            store.accept_event(self.db, "evt-1", "sensor.reading", {"temperature_c": 99})
        self.assertEqual(store.get_event(self.db, "evt-1")["payload"]["temperature_c"], 28.4)

    def test_http_failure_is_recorded_without_retry(self):
        self.submit()
        deliver_next(self.db, self.url + "/fail")
        result = store.get_event(self.db, "evt-1")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"][0]["http_status"], 503)
        self.assertFalse(deliver_next(self.db, self.url + "/webhook"))

    def test_connection_failure_is_recorded(self):
        self.submit()
        self.server.shutdown()
        self.server.server_close()
        deliver_next(self.db, self.url + "/webhook", timeout=0.3)
        result = store.get_event(self.db, "evt-1")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["attempts"][0]["http_status"])
        self.assertTrue(result["attempts"][0]["error"])

    def test_initializing_again_preserves_existing_event(self):
        self.submit()
        store.initialize(self.db)
        self.assertEqual(store.get_event(self.db, "evt-1")["status"], "pending")


if __name__ == "__main__":
    unittest.main()
