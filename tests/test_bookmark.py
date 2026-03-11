import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytz

import tap_ringcentral.cache
from tap_ringcentral.discover import discover
from tap_ringcentral.state import incorporate
from tap_ringcentral.streams import AVAILABLE_STREAMS

try:
    from .base import RingCentralBaseTest
except ImportError:
    from base import RingCentralBaseTest


class BookmarkIntegrationTest(RingCentralBaseTest, unittest.TestCase):
    """Verify that bookmarks (state) are correctly used and advanced during
    sync for the ContactBaseStream-derived streams (call_log,
    company_call_log, messages)."""

    def setUp(self):
        self.config = dict(self.DEFAULT_CONFIG)
        self.state = {}

    # ------------------------------------------------------------------
    # Test: existing bookmark is used as dateFrom
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_sync_uses_existing_bookmark(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """When state already contains a bookmark for ``company_call_log``,
        the sync should start from that bookmark instead of config start_date."""
        bookmark_value = "2025-06-01T00:00:00Z"
        self.state = incorporate(
            self.state, "company_call_log", "last_record", bookmark_value
        )

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record(
            "company_call_log", date_value="2025-06-05T00:00:00Z"
        )
        record["id"] = "ccl-bm-1"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        # Pin "now" just beyond bookmark + 7 days so the loop runs once
        fake_now = datetime(2025, 6, 8, 0, 0, 1, tzinfo=pytz.utc)

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
            self.state = stream_obj.state

        # The make_request call should have dateFrom based on the bookmark
        first_call_params = mock_client.make_request.call_args_list[0]
        params = first_call_params.kwargs.get("params") or first_call_params[1].get("params", {})
        self.assertIn("dateFrom", params)
        # The dateFrom should be the bookmark value (parsed then isoformatted)
        self.assertTrue(
            params["dateFrom"].startswith("2025-06-01"),
            f"Expected dateFrom to start with bookmark date, got {params['dateFrom']}",
        )

    # ------------------------------------------------------------------
    # Test: bookmark is advanced after sync
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_sync_advances_bookmark(
        self,
        _mock_write_schema,
        _mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """After syncing ``call_log``, the bookmark in state should be
        advanced to at least the start of the synced window."""
        old_bookmark = "2025-03-01T00:00:00Z"
        self.state = incorporate(
            self.state, "call_log", "last_record", old_bookmark
        )

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        records = [
            {**self._generate_stream_record("call_log", date_value="2025-03-02T00:00:00Z"), "id": "cl-1"},
            {**self._generate_stream_record("call_log", date_value="2025-03-05T00:00:00Z"), "id": "cl-2"},
        ]
        mock_client.make_request.return_value = self.make_call_log_api_response(records)

        # Populate contacts cache
        tap_ringcentral.cache.contacts = [{"id": 42, "name": "Ext User"}]

        fake_now = datetime(2025, 3, 8, 0, 0, 1, tzinfo=pytz.utc)

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
            self.state = stream_obj.state

        # The bookmark should have been advanced beyond the old value
        last_record = (
            self.state.get("bookmarks", {})
            .get("call_log", {})
            .get("last_record")
        )
        self.assertIsNotNone(last_record)
        self.assertGreaterEqual(last_record, old_bookmark)

    # ------------------------------------------------------------------
    # Test: bookmark is created for streams with no prior state
    # ------------------------------------------------------------------

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_bookmark_created_when_no_prior_state(
        self,
        _mock_write_schema,
        _mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """Starting with empty state, verify that a bookmark is created
        after syncing ``messages``."""
        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record("messages", date_value="2025-01-03T00:00:00Z")
        record["id"] = "msg-bm-1"
        mock_client.make_request.return_value = self.make_call_log_api_response([record])

        tap_ringcentral.cache.contacts = [{"id": 1, "name": "User"}]

        fake_now = datetime(2025, 1, 8, 0, 0, 1, tzinfo=pytz.utc)

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
            self.state = stream_obj.state

        self.assertIn("bookmarks", self.state)
        self.assertIn("messages", self.state["bookmarks"])
        self.assertIn("last_record", self.state["bookmarks"]["messages"])


if __name__ == "__main__":
    unittest.main()
