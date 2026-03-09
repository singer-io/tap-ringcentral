import unittest
from unittest.mock import patch, MagicMock
from tap_ringcentral.streams.base import BaseStream, ContactBaseStream


class TestBaseStream(unittest.TestCase):
    """
    Unit tests for the BaseStream class.

    This test class verifies that:
      - The stream initializes with the correct properties.
      - Schema loading works correctly.
      - Parameter generation is correct.
      - Record transformation works as expected.
      - The sync flow invokes the expected methods.
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

        # Mock catalog
        self.mock_catalog = MagicMock()
        self.mock_catalog.stream = "test_stream"
        self.mock_catalog.tap_stream_id = "test_stream"
        self.mock_catalog.schema.to_dict.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}}
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None

        # Mock client
        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    def test_init(self):
        """Test that the stream initializes with the correct properties."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        self.assertEqual(stream.config, self.config)
        self.assertEqual(stream.state, self.state)
        self.assertEqual(stream.catalog, self.mock_catalog)
        self.assertEqual(stream.client, self.mock_client)

    def test_key_properties(self):
        """Test that the default KEY_PROPERTIES is ['id']."""
        self.assertEqual(BaseStream.KEY_PROPERTIES, ['id'])

    def test_get_params_default(self):
        """Test that default parameters include page and per_page."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        params = stream.get_params(page=1)
        self.assertEqual(params, {"page": 1, "per_page": 1000})

    def test_get_params_custom_page(self):
        """Test that parameters respond to custom page numbers."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        params = stream.get_params(page=3)
        self.assertEqual(params["page"], 3)

    def test_get_body_returns_empty_dict(self):
        """Test that get_body returns an empty dictionary."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        self.assertEqual(stream.get_body(), {})

    @patch("singer.write_schema")
    def test_write_schema(self, mock_write_schema):
        """Test that write_schema calls singer.write_schema with correct arguments."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.write_schema()
        mock_write_schema.assert_called_once_with(
            "test_stream",
            {"type": "object", "properties": {"id": {"type": "string"}}},
            key_properties=["id"],
        )

    @patch.object(BaseStream, "sync_data")
    @patch("singer.write_schema")
    def test_sync_calls_write_schema_and_sync_data(self, mock_write_schema, mock_sync_data):
        """Test that sync calls write_schema and then sync_data."""
        stream = BaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.sync()
        mock_write_schema.assert_called_once()
        mock_sync_data.assert_called_once()


class TestContactBaseStream(unittest.TestCase):
    """
    Unit tests for the ContactBaseStream class.

    This test class verifies that:
      - The stream initializes with the correct properties.
      - Parameter generation includes date range and pagination.
      - The stream data transformation works correctly.
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

        # Mock catalog
        self.mock_catalog = MagicMock()
        self.mock_catalog.stream = "test_stream"
        self.mock_catalog.tap_stream_id = "test_stream"
        self.mock_catalog.schema.to_dict.return_value = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "_contact_id": {"type": "string"},
            }
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None

        # Mock client
        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    def test_key_properties(self):
        """Test that the default KEY_PROPERTIES is ['id']."""
        self.assertEqual(ContactBaseStream.KEY_PROPERTIES, ['id'])

    def test_get_params_includes_date_range(self):
        """Test that parameters include dateFrom, dateTo, showDeleted and pagination."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        params = stream.get_params(
            date_from="2025-01-01T00:00:00Z",
            date_to="2025-01-08T00:00:00Z",
            page=1,
            per_page=100
        )
        self.assertEqual(params["dateFrom"], "2025-01-01T00:00:00Z")
        self.assertEqual(params["dateTo"], "2025-01-08T00:00:00Z")
        self.assertEqual(params["page"], 1)
        self.assertEqual(params["perPage"], 100)
        self.assertTrue(params["showDeleted"])

    def test_get_stream_data_adds_contact_id(self):
        """Test that get_stream_data adds _contact_id to each record."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)

        # Mock transform_record to return the record as-is
        stream.transform_record = MagicMock(side_effect=lambda r: r)

        result = {"records": [{"id": "1"}, {"id": "2"}]}
        data = stream.get_stream_data(result, "ext123")

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["_contact_id"], "ext123")
        self.assertEqual(data[1]["_contact_id"], "ext123")


class TestContactsStream(unittest.TestCase):
    """
    Unit tests for the ContactsStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        from tap_ringcentral.streams.contacts import ContactsStream
        self.stream_class = ContactsStream

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
        self.mock_catalog.tap_stream_id = "contacts"
        self.mock_catalog.schema.to_dict.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}}
        }
        self.mock_catalog.key_properties = ["id"]
        self.mock_catalog.metadata = None
        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://platform.ringcentral.com"

    def test_stream_properties(self):
        """Test that ContactsStream has the correct properties."""
        self.assertEqual(self.stream_class.TABLE, "contacts")
        self.assertEqual(self.stream_class.KEY_PROPERTIES, ["id"])
        self.assertEqual(self.stream_class.API_METHOD, "GET")

    def test_api_path(self):
        """Test that the api_path property returns the correct URL path."""
        stream = self.stream_class(self.config, self.state, self.mock_catalog, self.mock_client)
        self.assertEqual(stream.api_path, "/restapi/v1.0/account/~/directory/entries")


class TestCallLogStream(unittest.TestCase):
    """
    Unit tests for the CallLogStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        from tap_ringcentral.streams.call_log import CallLogStream
        self.stream_class = CallLogStream

    def test_stream_properties(self):
        """Test that CallLogStream has the correct properties."""
        self.assertEqual(self.stream_class.TABLE, "call_log")
        self.assertEqual(self.stream_class.KEY_PROPERTIES, ["id"])
        self.assertEqual(self.stream_class.API_METHOD, "GET")

    def test_api_path(self):
        """Test that the api_path property returns the correct URL path with extensionId placeholder."""
        config = {
            "client_id": "test", "client_secret": "test",
            "refresh_token": "test", "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        mock_catalog = MagicMock()
        mock_catalog.stream = "call_log"
        mock_catalog.metadata = None
        mock_client = MagicMock()
        stream = self.stream_class(config, {}, mock_catalog, mock_client)
        self.assertEqual(stream.api_path, "/restapi/v1.0/account/~/extension/{extensionId}/call-log")


class TestCompanyCallLogStream(unittest.TestCase):
    """
    Unit tests for the CompanyCallLogStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        from tap_ringcentral.streams.company_call_log import CompanyCallLogStream
        self.stream_class = CompanyCallLogStream

    def test_stream_properties(self):
        """Test that CompanyCallLogStream has the correct properties."""
        self.assertEqual(self.stream_class.TABLE, "company_call_log")
        self.assertEqual(self.stream_class.KEY_PROPERTIES, ["id"])
        self.assertEqual(self.stream_class.API_METHOD, "GET")

    def test_api_path(self):
        """Test that the api_path property returns the correct URL path."""
        config = {
            "client_id": "test", "client_secret": "test",
            "refresh_token": "test", "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        mock_catalog = MagicMock()
        mock_catalog.stream = "company_call_log"
        mock_catalog.metadata = None
        mock_client = MagicMock()
        stream = self.stream_class(config, {}, mock_catalog, mock_client)
        self.assertEqual(stream.api_path, "/restapi/v1.0/account/~/call-log")


class TestMessageStream(unittest.TestCase):
    """
    Unit tests for the MessageStream class.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        from tap_ringcentral.streams.messages import MessageStream
        self.stream_class = MessageStream

    def test_stream_properties(self):
        """Test that MessageStream has the correct properties."""
        self.assertEqual(self.stream_class.TABLE, "messages")
        self.assertEqual(self.stream_class.KEY_PROPERTIES, ["id"])
        self.assertEqual(self.stream_class.API_METHOD, "GET")

    def test_api_path(self):
        """Test that the api_path property returns the correct URL path with extensionId placeholder."""
        config = {
            "client_id": "test", "client_secret": "test",
            "refresh_token": "test", "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        mock_catalog = MagicMock()
        mock_catalog.stream = "messages"
        mock_catalog.metadata = None
        mock_client = MagicMock()
        stream = self.stream_class(config, {}, mock_catalog, mock_client)
        self.assertEqual(stream.api_path, "/restapi/v1.0/account/~/extension/{extensionId}/message-store")


if __name__ == "__main__":
    unittest.main()
