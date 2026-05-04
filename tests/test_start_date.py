import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytz

import tap_ringcentral.cache
from tap_ringcentral.discover import discover
from tap_ringcentral.streams import AVAILABLE_STREAMS

try:
    from .base import RingCentralBaseTest
except ImportError:
    from base import RingCentralBaseTest


class StartDateIntegrationTest(RingCentralBaseTest, unittest.TestCase):
    """Verify that the config ``start_date`` is honoured when no bookmark
    exists in state – closely matching the saasquatch start-date tests."""

    def setUp(self):
        self.config = dict(self.DEFAULT_CONFIG)
        self.state = {}

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_sync_starts_from_config_start_date_when_no_bookmark(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """With empty state the first ``dateFrom`` passed to the API should
        be derived from ``config.start_date``."""
        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record(
            "company_call_log", date_value="2025-01-03T00:00:00Z"
        )
        record["id"] = "ccl-sd-1"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        # Pin "now" so the 7-day window loop runs once
        fake_now = datetime(2025, 1, 8, 0, 0, 1, tzinfo=pytz.utc)

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

        # Verify dateFrom in the first API call matches the config start_date
        first_call = mock_client.make_request.call_args_list[0]
        params = first_call.kwargs.get("params") or first_call[1].get("params", {})
        self.assertIn("dateFrom", params)
        self.assertTrue(
            params["dateFrom"].startswith("2025-01-01"),
            f"Expected dateFrom to start with config start_date, got {params['dateFrom']}",
        )

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_updated_start_date_is_reflected(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """When the config start_date is changed, the new value should be used."""
        self.config["start_date"] = "2025-04-20T10:30:00Z"

        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record(
            "company_call_log", date_value="2025-04-22T00:00:00Z"
        )
        record["id"] = "ccl-sd-2"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        fake_now = datetime(2025, 4, 28, 0, 0, 1, tzinfo=pytz.utc)

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

        first_call = mock_client.make_request.call_args_list[0]
        params = first_call.kwargs.get("params") or first_call[1].get("params", {})
        self.assertTrue(
            params["dateFrom"].startswith("2025-04-20"),
            f"Expected dateFrom from updated start_date, got {params['dateFrom']}",
        )

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("singer.write_records")
    @patch("singer.write_schema")
    def test_call_log_uses_start_date_per_extension(
        self,
        _mock_write_schema,
        mock_write_records,
        _mock_save_state,
        _mock_sleep,
    ):
        """For extension-based streams (call_log, messages), the start_date
        should still be used as the initial dateFrom for each extension."""
        mock_client = MagicMock()
        mock_client.base_url = self.config["api_url"]

        record = self._generate_stream_record(
            "call_log", date_value="2025-01-03T00:00:00Z"
        )
        record["id"] = "cl-sd-1"
        mock_client.make_request.return_value = self.make_call_log_api_response(
            [record]
        )

        # Two extensions in cache
        tap_ringcentral.cache.contacts = [
            {"id": 10, "name": "Ext-A"},
            {"id": 20, "name": "Ext-B"},
        ]

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

        # Should have made one API call per extension
        self.assertEqual(mock_client.make_request.call_count, 2)

        for api_call in mock_client.make_request.call_args_list:
            params = api_call.kwargs.get("params") or api_call[1].get("params", {})
            self.assertTrue(
                params["dateFrom"].startswith("2025-01-01"),
                f"Expected dateFrom from config start_date, got {params['dateFrom']}",
            )


if __name__ == "__main__":
    unittest.main()
