import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytz

import tap_ringcentral.cache
from tap_ringcentral.discover import discover
from tap_ringcentral.streams import AVAILABLE_STREAMS
from tap_ringcentral import RingCentralRunner

try:
    from .base import RingCentralBaseTest
except ImportError:
    from base import RingCentralBaseTest


class SyncIntegrationTest(RingCentralBaseTest, unittest.TestCase):
    """End-to-end sync tests using mocked RingCentral API responses.

    These mirror the ``test_sync.py`` from tap-referral-saasquatch but
    exercise RingCentral-specific pagination, contact-based extension
    iteration, and the ``RingCentralRunner.do_sync`` orchestrator.
    """

    def setUp(self):
        self.config = dict(self.DEFAULT_CONFIG)
        self.state = {}

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_runner(self, catalog, mock_client):
        """Build a ``RingCentralRunner`` with a lightweight args object."""
        args = MagicMock()
        args.config = self.config
        args.state = self.state
        args.catalog = catalog
        return RingCentralRunner(args, mock_client)

    # ------------------------------------------------------------------
    # Test: contacts pagination
    # ------------------------------------------------------------------

    @patch("singer.write_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_contacts_pagination(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_write_state,
    ):
        """Contacts should page through all totalPages returned by the API."""
        page1_records = [
            {**self._generate_stream_record("contacts"), "id": i}
            for i in range(1, 4)
        ]
        page2_records = [
            {**self._generate_stream_record("contacts"), "id": i}
            for i in range(4, 6)
        ]

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        # First call → page 1/2, second call → page 2/2
        mock_client.make_request.side_effect = [
            self.make_contacts_api_response(page1_records, page=1, total_pages=2),
            self.make_contacts_api_response(page2_records, page=2, total_pages=2),
        ]

        catalog = discover()
        contacts_entry = [
            s for s in catalog.streams if s.tap_stream_id == "contacts"
        ][0]

        stream_cls = AVAILABLE_STREAMS["contacts"]
        stream_obj = stream_cls(self.config, {}, contacts_entry, mock_client)
        stream_obj.sync()

        self.assertEqual(mock_client.make_request.call_count, 2)

        total_written = sum(
            len(c.args[1])
            for c in mock_write_records.call_args_list
            if c.args[0] == "contacts"
        )
        self.assertEqual(total_written, 5)

    # ------------------------------------------------------------------
    # Test: extension-based streams iterate over cached contacts
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_call_log_iterates_over_extensions(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """``call_log`` should make one API call per cached contact/extension."""
        tap_ringcentral.cache.contacts = [
            {"id": 100, "name": "Ext-1"},
            {"id": 200, "name": "Ext-2"},
            {"id": 300, "name": "Ext-3"},
        ]

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record("call_log", date_value="2025-01-02T00:00:00Z")
        record["id"] = "cl-ext"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        fake_now = datetime(2025, 1, 8, 0, 0, 0, tzinfo=pytz.utc)

        catalog = discover()
        call_log_entry = [
            s for s in catalog.streams if s.tap_stream_id == "call_log"
        ][0]

        stream_cls = AVAILABLE_STREAMS["call_log"]

        with patch("tap_ringcentral.streams.base.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            stream_obj = stream_cls(
                self.config, self.state, call_log_entry, mock_client
            )
            stream_obj.sync()

        # One API call per extension
        self.assertEqual(mock_client.make_request.call_count, 3)

        # Verify the URLs contain the extension IDs
        urls_called = [c.args[0] for c in mock_client.make_request.call_args_list]
        self.assertTrue(any("100" in url for url in urls_called))
        self.assertTrue(any("200" in url for url in urls_called))
        self.assertTrue(any("300" in url for url in urls_called))

    # ------------------------------------------------------------------
    # Test: company_call_log does NOT iterate extensions
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_company_call_log_single_api_call(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """``company_call_log`` calls the account-level endpoint once per
        7-day window (not per extension)."""
        tap_ringcentral.cache.contacts = [
            {"id": 100, "name": "Ext-1"},
            {"id": 200, "name": "Ext-2"},
        ]

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record(
            "company_call_log", date_value="2025-01-02T00:00:00Z"
        )
        record["id"] = "ccl-single"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        fake_now = datetime(2025, 1, 8, 0, 0, 0, tzinfo=pytz.utc)

        catalog = discover()
        company_cl_entry = [
            s for s in catalog.streams if s.tap_stream_id == "company_call_log"
        ][0]

        stream_cls = AVAILABLE_STREAMS["company_call_log"]

        with patch("tap_ringcentral.streams.base.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            stream_obj = stream_cls(
                self.config, self.state, company_cl_entry, mock_client
            )
            stream_obj.sync()

        # Only one API call (not per-extension)
        self.assertEqual(mock_client.make_request.call_count, 1)

    # ------------------------------------------------------------------
    # Test: do_sync via RingCentralRunner
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_runner_do_sync_invokes_all_selected_streams(
        self,
        _mock_write_schema,
        mock_write_records,
        mock_write_state,
        _mock_save_state,
        _mock_sleep,
    ):
        """``RingCentralRunner.do_sync`` should invoke sync for every
        selected stream and call ``save_state`` at the end."""
        tap_ringcentral.cache.contacts = [{"id": 1, "name": "User"}]

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        contacts_rec = {**self._generate_stream_record("contacts"), "id": 1}
        call_log_rec = {**self._generate_stream_record("call_log", "2025-01-02T00:00:00Z"), "id": "cl-r"}
        company_rec = {**self._generate_stream_record("company_call_log", "2025-01-02T00:00:00Z"), "id": "ccl-r"}
        messages_rec = {**self._generate_stream_record("messages", "2025-01-02T00:00:00Z"), "id": "msg-r"}

        def side_effect(url, method, params=None, body=None):
            if "/directory/entries" in url:
                return self.make_contacts_api_response([contacts_rec])
            if "/extension/" in url and "/call-log" in url:
                return self.make_call_log_api_response([call_log_rec])
            if "/account/~/call-log" in url:
                return self.make_call_log_api_response([company_rec])
            if "/message-store" in url:
                return self.make_call_log_api_response([messages_rec])
            return {"records": [], "paging": {"page": 1, "totalPages": 1, "perPage": 1000}}

        mock_client.make_request.side_effect = side_effect

        fake_now = datetime(2025, 1, 8, 0, 0, 1, tzinfo=pytz.utc)

        catalog = discover()
        catalog.get_selected_streams = lambda _state: catalog.streams

        with patch("tap_ringcentral.streams.base.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            runner = self._make_runner(catalog, mock_client)
            runner.do_sync()

        written_streams = {
            c.args[0] for c in mock_write_records.call_args_list
        }
        self.assertEqual(
            written_streams,
            {"contacts", "call_log", "company_call_log", "messages"},
        )

        mock_write_state.assert_called()

    # ------------------------------------------------------------------
    # Test: multiple 7-day windows
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_messages_syncs_multiple_windows(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """If the date range spans more than 7 days, multiple windows are
        synced with separate API calls."""
        tap_ringcentral.cache.contacts = [{"id": 1, "name": "User"}]

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record("messages", date_value="2025-01-05T00:00:00Z")
        record["id"] = "msg-mw"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        # 15 days from start → should be 3 windows (0-7, 7-14, 14-15)
        fake_now = datetime(2025, 1, 16, 0, 0, 1, tzinfo=pytz.utc)

        catalog = discover()
        messages_entry = [
            s for s in catalog.streams if s.tap_stream_id == "messages"
        ][0]

        stream_cls = AVAILABLE_STREAMS["messages"]

        with patch("tap_ringcentral.streams.base.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            stream_obj = stream_cls(
                self.config, self.state, messages_entry, mock_client
            )
            stream_obj.sync()

        # 1 extension × 3 windows = 3 API calls
        self.assertEqual(mock_client.make_request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
