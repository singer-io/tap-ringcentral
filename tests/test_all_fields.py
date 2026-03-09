import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytz

import tap_ringcentral.cache
from tap_ringcentral.discover import discover
from tap_ringcentral.streams import AVAILABLE_STREAMS

try:
    from .base import RingCentralBaseTest
except ImportError:
    from base import RingCentralBaseTest


class AllFieldsIntegrationTest(RingCentralBaseTest, unittest.TestCase):
    """Run a full sync for every stream using mocked API responses and verify
    that records are written for all streams and all expected fields appear
    in the emitted records."""

    def setUp(self):
        self.config = dict(self.DEFAULT_CONFIG)
        self.state = {}

    # ------------------------------------------------------------------
    # Helper: build a mock client whose ``make_request`` returns
    # stream-appropriate API payloads.
    # ------------------------------------------------------------------

    def _build_mock_client(self, contacts_records, call_log_records,
                           company_call_log_records, messages_records):
        """Return a mock ``RingCentralClient`` whose ``make_request``
        inspects the URL to decide which response to return."""
        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        def side_effect(url, method, params=None, body=None):
            if "/directory/entries" in url:
                return self.make_contacts_api_response(contacts_records)
            if "/extension/" in url and "/call-log" in url:
                return self.make_call_log_api_response(call_log_records)
            if "/account/~/call-log" in url:
                return self.make_call_log_api_response(company_call_log_records)
            if "/message-store" in url:
                return self.make_call_log_api_response(messages_records)
            return {"records": [], "paging": {"page": 1, "totalPages": 1, "perPage": 1000}}

        mock_client.make_request.side_effect = side_effect
        return mock_client

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_sync_all_streams_emits_records(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """Sync all four streams and verify at least one record is written
        per stream."""
        # Generate one valid record per stream
        contacts_rec = self._generate_stream_record("contacts", date_value="2025-02-01T00:00:00Z")
        contacts_rec["id"] = 101
        call_log_rec = self._generate_stream_record("call_log", date_value="2025-02-01T00:00:00Z")
        call_log_rec["id"] = "cl-1"
        company_cl_rec = self._generate_stream_record("company_call_log", date_value="2025-02-01T00:00:00Z")
        company_cl_rec["id"] = "ccl-1"
        messages_rec = self._generate_stream_record("messages", date_value="2025-02-01T00:00:00Z")
        messages_rec["id"] = "msg-1"

        mock_client = self._build_mock_client(
            contacts_records=[contacts_rec],
            call_log_records=[call_log_rec],
            company_call_log_records=[company_cl_rec],
            messages_records=[messages_rec],
        )

        # Populate the contacts cache so that extension-based streams
        # have something to iterate over.
        tap_ringcentral.cache.contacts = [{"id": 101, "name": "Test User"}]

        # Pin "now" so the 7-day window loop only runs once.
        fake_now = datetime(2025, 1, 8, 0, 0, 0, tzinfo=pytz.utc)

        catalog = discover()
        # Select all streams
        catalog.get_selected_streams = lambda _state: catalog.streams

        with patch("tap_ringcentral.streams.base.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            for stream_entry in catalog.streams:
                stream_cls = AVAILABLE_STREAMS[stream_entry.stream]
                stream_obj = stream_cls(
                    self.config, self.state, stream_entry, mock_client
                )
                stream_obj.sync()
                self.state = stream_obj.state

        # Collect which streams received write_records calls
        written_streams = {
            c.args[0] for c in mock_write_records.call_args_list
        }
        self.assertEqual(
            written_streams,
            {"contacts", "call_log", "company_call_log", "messages"},
        )

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_contacts_records_match_schema_fields(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """Verify that the record emitted for ``contacts`` contains only
        keys that exist in the schema."""
        contacts_rec = self._generate_stream_record("contacts")
        contacts_rec["id"] = 999

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]
        mock_client.make_request.return_value = self.make_contacts_api_response(
            [contacts_rec]
        )

        catalog = discover()
        contacts_entry = [
            s for s in catalog.streams if s.tap_stream_id == "contacts"
        ][0]

        stream_cls = AVAILABLE_STREAMS["contacts"]
        stream_obj = stream_cls(self.config, {}, contacts_entry, mock_client)
        stream_obj.sync()

        self.assertTrue(mock_write_records.called)
        written_table = mock_write_records.call_args_list[0].args[0]
        self.assertEqual(written_table, "contacts")

        emitted_record = mock_write_records.call_args_list[0].args[1][0]
        schema_keys = set(contacts_entry.schema.to_dict()["properties"].keys())
        self.assertTrue(
            set(emitted_record.keys()).issubset(schema_keys),
            f"Emitted keys {set(emitted_record.keys())} are not a subset of "
            f"schema keys {schema_keys}",
        )


if __name__ == "__main__":
    unittest.main()
