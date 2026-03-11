import unittest
from unittest.mock import patch, MagicMock
from singer.catalog import Catalog
from tap_ringcentral.discover import discover


class TestDiscover(unittest.TestCase):
    """
    Unit tests for the `discover` function in the tap_ringcentral.discover module.

    This test class verifies that:
      - The discover function returns a valid Catalog object.
      - All expected streams are present in the catalog.
      - Each stream has the correct key properties and metadata.
    """

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_returns_catalog(self, mock_get_schemas):
        """Test that discover returns a Catalog instance."""
        mock_get_schemas.return_value = (
            {
                "contacts": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}}
                }
            },
            {
                "contacts": [
                    {"breadcrumb": (), "metadata": {"table-key-properties": ["id"]}}
                ]
            },
        )

        catalog = discover()
        self.assertIsInstance(catalog, Catalog)

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_has_expected_streams(self, mock_get_schemas):
        """Test that discover returns all expected streams."""
        schemas = {}
        field_metadata = {}
        for stream_name in ["contacts", "call_log", "company_call_log", "messages"]:
            schemas[stream_name] = {
                "type": "object",
                "properties": {"id": {"type": "string"}}
            }
            field_metadata[stream_name] = [
                {"breadcrumb": (), "metadata": {"table-key-properties": ["id"]}}
            ]

        mock_get_schemas.return_value = (schemas, field_metadata)

        catalog = discover()
        stream_names = [entry.stream for entry in catalog.streams]

        self.assertIn("contacts", stream_names)
        self.assertIn("call_log", stream_names)
        self.assertIn("company_call_log", stream_names)
        self.assertIn("messages", stream_names)
        self.assertEqual(len(catalog.streams), 4)

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_stream_has_key_properties(self, mock_get_schemas):
        """Test that each discovered stream has the correct key properties."""
        mock_get_schemas.return_value = (
            {
                "contacts": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}}
                }
            },
            {
                "contacts": [
                    {"breadcrumb": (), "metadata": {"table-key-properties": ["id"]}}
                ]
            },
        )

        catalog = discover()
        contacts_entry = catalog.streams[0]
        self.assertEqual(contacts_entry.key_properties, ["id"])


class TestGetSchemas(unittest.TestCase):
    """
    Unit tests for the `get_schemas` function in the tap_ringcentral.schema module.

    This test class verifies that:
      - Schemas are loaded for all available streams.
      - Field metadata is populated correctly.
    """

    @patch("tap_ringcentral.schema.open", create=True)
    @patch("tap_ringcentral.schema.json.load")
    def test_get_schemas_returns_all_streams(self, mock_json_load, mock_open):
        """Test that get_schemas returns schemas for all available streams."""
        mock_json_load.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}}
        }

        from tap_ringcentral.schema import get_schemas
        schemas, field_metadata = get_schemas()

        expected_streams = ["contacts", "call_log", "company_call_log", "messages"]
        for stream_name in expected_streams:
            self.assertIn(stream_name, schemas)
            self.assertIn(stream_name, field_metadata)


if __name__ == "__main__":
    unittest.main()
