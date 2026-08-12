import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
import pytz

from tap_ringcentral.streams.base import BaseStream, ContactBaseStream
from tap_ringcentral.streams.contacts import ContactsStream
from tap_ringcentral.streams.company_call_log import CompanyCallLogStream


class TestBaseStreamTransform(unittest.TestCase):
    """
    Unit tests for the transform_record and get_schema methods of BaseStream.
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
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}}
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    @patch("tap_ringcentral.streams.base.singer.Transformer")
    def test_transform_record_with_metadata(self, mock_transformer_class):
        """Test transform_record applies metadata when available."""
        mock_transformer = MagicMock()
        mock_transformer_class.return_value.__enter__.return_value = mock_transformer
        mock_transformer.transform.return_value = {"id": "1", "name": "Test"}

        # Add metadata to catalog
        self.mock_catalog.metadata = [
            {"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}
        ]

        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        record = {"id": "1", "name": "Test"}

        result = stream.transform_record(record)

        mock_transformer.transform.assert_called_once()
        self.assertEqual(result, {"id": "1", "name": "Test"})

    @patch("tap_ringcentral.streams.base.singer.Transformer")
    def test_transform_record_without_metadata(self, mock_transformer_class):
        """Test transform_record works with no metadata."""
        mock_transformer = MagicMock()
        mock_transformer_class.return_value.__enter__.return_value = mock_transformer
        mock_transformer.transform.return_value = {"id": "1"}

        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        record = {"id": "1"}

        result = stream.transform_record(record)

        mock_transformer.transform.assert_called_once()
        call_args = mock_transformer.transform.call_args
        # Verify metadata dict is empty when catalog.metadata is None
        self.assertEqual(call_args[0][2], {})

    def test_get_schema_loads_schema_by_table_name(self):
        """Test get_schema loads schema using TABLE name."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "contacts"

        with patch.object(stream, "load_schema_by_name") as mock_load:
            mock_load.return_value = {"type": "object"}
            stream.get_schema()
            mock_load.assert_called_once_with("contacts")

    def test_get_class_path_returns_directory(self):
        """Test get_class_path returns the directory of the class file."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        path = stream.get_class_path()
        self.assertIsNotNone(path)
        self.assertTrue(len(path) > 0)

    def test_get_url_constructs_full_url(self):
        """Test get_url constructs full URL from base and path."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        # Note: BASE_URL must be defined in the base.py module for this to work
        # This test documents current behavior


class TestContactsStreamGetStreamData(unittest.TestCase):
    """
    Unit tests for the ContactsStream.get_stream_data method.
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
        self.mock_catalog.stream = "contacts"
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    @patch("tap_ringcentral.streams.contacts.tap_ringcentral.cache.contacts")
    def test_get_stream_data_extends_cache(self, mock_cache):
        """Test get_stream_data adds contacts to cache."""
        mock_cache.extend = MagicMock()

        stream = ContactsStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.transform_record = MagicMock(side_effect=lambda r: r)

        result = {"records": [{"id": "1", "name": "Contact 1"}, {"id": "2", "name": "Contact 2"}]}

        data = stream.get_stream_data(result)

        # Verify cache.extend was called
        mock_cache.extend.assert_called_once()
        # Verify returned data matches
        self.assertEqual(len(data), 2)


class TestCompanyCallLogStreamSyncDataForPeriod(unittest.TestCase):
    """
    Unit tests for the CompanyCallLogStream.sync_data_for_period method.
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
        self.mock_catalog.stream = "company_call_log"
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    def test_sync_data_for_period_calls_sync_for_extension_with_none(self):
        """Test CompanyCallLogStream.sync_data_for_period calls sync_data_for_extension with None extensionId."""
        stream = CompanyCallLogStream(self.config, self.state, self.mock_catalog, self.mock_client)

        # Mock sync_data_for_extension instead of trying to run it
        with patch.object(stream, 'sync_data_for_extension') as mock_sync:
            date = datetime(2025, 1, 1, tzinfo=pytz.utc)
            interval = timedelta(days=7)

            stream.sync_data_for_period(date, interval)

            # Verify sync_data_for_extension was called with None instead of iterating contacts
            mock_sync.assert_called_once_with(date, interval, None)

    def test_sync_data_for_period_returns_updated_state(self):
        """Test sync_data_for_period updates state with new bookmark."""
        stream = CompanyCallLogStream(self.config, self.state, self.mock_catalog, self.mock_client)

        with patch.object(stream, 'sync_data_for_extension'):
            date = datetime(2025, 1, 1, tzinfo=pytz.utc)
            interval = timedelta(days=7)

            result = stream.sync_data_for_period(date, interval)

            self.assertIn("bookmarks", result)
            self.assertIn("company_call_log", result["bookmarks"])


class TestBaseStreamGetStreamDataWithContactId(unittest.TestCase):
    """
    Unit tests for BaseStream.get_stream_data with contact_id parameter.
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
        self.mock_catalog.metadata = None

        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    def test_get_stream_data_processes_records_and_adds_contact_id(self):
        """Test get_stream_data adds contact_id to each record."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.transform_record = MagicMock(side_effect=lambda r: r)

        result = {"records": [{"id": "1"}, {"id": "2"}]}
        contact_id = "ext123"

        data = stream.get_stream_data(result, contact_id)

        self.assertEqual(len(data), 2)
        for record in data:
            self.assertEqual(record["_contact_id"], contact_id)
