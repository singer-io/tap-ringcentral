import unittest
from unittest.mock import patch, MagicMock, call
import time
from datetime import datetime, timedelta
import pytz

from tap_ringcentral.streams.base import BaseStream, ContactBaseStream
from tap_ringcentral.client import RingCentralForbiddenError


class TestBaseStreamSyncData(unittest.TestCase):
    """
    Unit tests for the sync_data method of BaseStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        self.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        self.state = {}

        self.mock_catalog = MagicMock()
        self.mock_catalog.stream = "test_stream"
        self.mock_catalog.tap_stream_id = "test_stream"
        self.mock_catalog.schema.to_dict.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}}
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    @patch("tap_ringcentral.streams.base.singer.write_records")
    @patch("tap_ringcentral.streams.base.singer.metrics.record_counter")
    def test_sync_data_single_page(self, mock_counter_context, mock_write_records):
        """Test sync_data with single page of results."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path"

        # Mock transform_record to return record as-is
        stream.transform_record = MagicMock(side_effect=lambda r: r)

        # Override get_stream_data to handle no contact_id
        stream.get_stream_data = MagicMock(return_value=[{"id": "1", "name": "Test 1"}])

        # Mock API response
        self.mock_client.make_request.return_value = {
            "records": [{"id": "1", "name": "Test 1"}],
            "paging": {"totalPages": 1}
        }

        # Mock the record counter context manager
        mock_counter = MagicMock()
        mock_counter_context.return_value.__enter__.return_value = mock_counter

        stream.sync_data()

        # Verify API was called
        self.mock_client.make_request.assert_called_once()
        # Verify records were written
        mock_write_records.assert_called_once()

    @patch("tap_ringcentral.streams.base.singer.write_records")
    @patch("tap_ringcentral.streams.base.singer.metrics.record_counter")
    def test_sync_data_multiple_pages(self, mock_counter_context, mock_write_records):
        """Test sync_data with multiple pages of results."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path"

        stream.transform_record = MagicMock(side_effect=lambda r: r)
        stream.get_stream_data = MagicMock(side_effect=[
            [{"id": "1"}],
            [{"id": "2"}]
        ])

        # Mock API responses for pages 1 and 2
        page_1_response = {
            "records": [{"id": "1"}],
            "paging": {"totalPages": 2}
        }
        page_2_response = {
            "records": [{"id": "2"}],
            "paging": {"totalPages": 2}
        }

        self.mock_client.make_request.side_effect = [page_1_response, page_2_response]

        mock_counter = MagicMock()
        mock_counter_context.return_value.__enter__.return_value = mock_counter

        stream.sync_data()

        # Verify API was called twice
        self.assertEqual(self.mock_client.make_request.call_count, 2)
        # Verify records were written twice
        self.assertEqual(mock_write_records.call_count, 2)

    def test_check_access_returns_true_for_accessible_stream(self):
        """Test check_access returns True when stream is accessible."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.api_path = "/test/path"
        stream.API_METHOD = "GET"

        # Mock successful API call
        self.mock_client.make_request.return_value = {"data": "success"}

        result = stream.check_access()

        self.assertTrue(result)
        self.mock_client.make_request.assert_called_once()

    def test_check_access_returns_false_for_forbidden_stream(self):
        """Test check_access returns False when stream returns 403 Forbidden."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.api_path = "/test/path"
        stream.API_METHOD = "GET"

        # Mock forbidden error
        self.mock_client.make_request.side_effect = RingCentralForbiddenError("HTTP-error-code: 403")

        result = stream.check_access()

        self.assertFalse(result)

    def test_check_access_always_true_for_child_stream(self):
        """Test check_access returns True for child streams."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.parent = "parent_stream"

        result = stream.check_access()

        self.assertTrue(result)
        # Verify API was NOT called for child stream
        self.mock_client.make_request.assert_not_called()

    def test_check_access_replaces_placeholders_in_url(self):
        """Test check_access replaces placeholders with ~ in URL."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.api_path = "/restapi/v1.0/account/~/extension/{extensionId}/call-log"
        stream.API_METHOD = "GET"

        self.mock_client.make_request.return_value = {"data": "success"}

        stream.check_access()

        # Verify the URL passed has placeholders replaced with ~
        call_args = self.mock_client.make_request.call_args
        called_url = call_args[0][0]
        self.assertIn("~/extension/~", called_url)


class TestContactBaseStreamSyncData(unittest.TestCase):
    """
    Unit tests for the sync_data and related methods of ContactBaseStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        self.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        self.state = {}

        self.mock_catalog = MagicMock()
        self.mock_catalog.stream = "test_stream"
        self.mock_catalog.tap_stream_id = "test_stream"
        self.mock_catalog.schema.to_dict.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}}
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    @patch("tap_ringcentral.streams.base.tap_ringcentral.cache.contacts", [])
    @patch("tap_ringcentral.streams.base.save_state")
    @patch("tap_ringcentral.streams.base.get_last_record_value_for_table")
    @patch("tap_ringcentral.streams.base.get_config_start_date")
    def test_sync_data_with_no_previous_state(self, mock_get_start_date, mock_get_last_record, mock_save_state):
        """Test sync_data uses start_date when no previous state exists."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path/{extensionId}"

        # Mock no previous bookmark
        mock_get_last_record.return_value = None
        start_date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        mock_get_start_date.return_value = start_date

        # Mock sync_data_for_period
        stream.sync_data_for_period = MagicMock()

        stream.sync_data()

        # Verify get_config_start_date was called
        mock_get_start_date.assert_called_once_with(self.config)

    @patch("tap_ringcentral.streams.base.save_state")
    def test_sync_data_for_period_returns_updated_state(self, mock_save_state):
        """Test sync_data_for_period returns updated state."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"

        # Mock sync_data_for_extension
        stream.sync_data_for_extension = MagicMock()

        date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        interval = timedelta(days=7)

        with patch("tap_ringcentral.streams.base.tap_ringcentral.cache.contacts", []):
            result = stream.sync_data_for_period(date, interval)

        self.assertIsNotNone(result)
        self.assertIn("bookmarks", result)

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.singer.write_records")
    @patch("tap_ringcentral.streams.base.singer.metrics.record_counter")
    def test_sync_data_for_extension_handles_pagination(self, mock_counter_context, mock_write_records, mock_sleep):
        """Test sync_data_for_extension stops pagination when data is less than per_page."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path/{extensionId}"

        stream.transform_record = MagicMock(side_effect=lambda r: r)

        # Mock API response with fewer records than per_page
        self.mock_client.make_request.return_value = {
            "records": [{"id": "1"}],  # Only 1 record, less than per_page=100
        }

        mock_counter = MagicMock()
        mock_counter_context.return_value.__enter__.return_value = mock_counter

        date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        interval = timedelta(days=7)

        stream.sync_data_for_extension(date, interval, "ext123")

        # Verify API was called once (no pagination)
        self.mock_client.make_request.assert_called_once()
        # Verify sleep was called for rate limiting
        mock_sleep.assert_called()

    @patch("tap_ringcentral.streams.base.time.sleep")
    @patch("tap_ringcentral.streams.base.singer.write_records")
    @patch("tap_ringcentral.streams.base.singer.metrics.record_counter")
    def test_sync_data_for_extension_continues_pagination(self, mock_counter_context, mock_write_records, mock_sleep):
        """Test sync_data_for_extension continues pagination when data reaches per_page."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "test_table"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path/{extensionId}"

        stream.transform_record = MagicMock(side_effect=lambda r: r)

        # First page has 100 records, second page has fewer
        page_1 = {"records": [{"id": str(i)} for i in range(100)]}
        page_2 = {"records": [{"id": "101"}]}

        self.mock_client.make_request.side_effect = [page_1, page_2]

        mock_counter = MagicMock()
        mock_counter_context.return_value.__enter__.return_value = mock_counter

        date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        interval = timedelta(days=7)

        stream.sync_data_for_extension(date, interval, "ext123")

        # Verify API was called twice
        self.assertEqual(self.mock_client.make_request.call_count, 2)

    @patch("tap_ringcentral.streams.base.time.sleep")
    def test_sync_data_for_extension_handles_forbidden_error(self, mock_sleep):
        """Test sync_data_for_extension handles RingCentralForbiddenError gracefully."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "messages"
        stream.API_METHOD = "GET"
        stream.api_path = "/test/path/{extensionId}"

        stream.transform_record = MagicMock(side_effect=lambda r: r)

        # Mock API to raise forbidden error
        self.mock_client.make_request.side_effect = RingCentralForbiddenError(
            "HTTP-error-code: 403, No permission for this extension"
        )

        date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        interval = timedelta(days=7)

        # Should NOT raise exception
        stream.sync_data_for_extension(date, interval, "ext123")

        # Verify the forbidden error was caught
        self.mock_client.make_request.assert_called_once()
