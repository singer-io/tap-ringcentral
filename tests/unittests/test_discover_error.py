import unittest
from unittest.mock import patch, MagicMock

from tap_ringcentral.discover import discover
from singer.catalog import Catalog


class TestDiscoverSchemaException(unittest.TestCase):
    """
    Unit tests for discover function error handling when schema is invalid.
    """

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_schema_exception_handling(self, mock_get_schemas):
        """Test discover raises and logs exception when schema is invalid."""
        # Simulate a bad schema dict
        mock_get_schemas.return_value = (
            {"contacts": None},  # Invalid schema (None instead of dict)
            {"contacts": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}]}
        )

        with self.assertRaises(Exception):
            discover(client=None)


class TestDiscoverMultipleStreams(unittest.TestCase):
    """
    Unit tests for discover function with multiple streams.
    """

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_returns_all_streams(self, mock_get_schemas):
        """Test discover returns all available streams in catalog."""
        mock_get_schemas.return_value = (
            {
                "contacts": {"type": "object", "properties": {}},
                "call_log": {"type": "object", "properties": {}},
                "messages": {"type": "object", "properties": {}},
            },
            {
                "contacts": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}],
                "call_log": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}],
                "messages": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}],
            }
        )

        catalog = discover(client=None)

        self.assertEqual(len(catalog.streams), 3)
        stream_names = {s.stream for s in catalog.streams}
        self.assertEqual(stream_names, {"contacts", "call_log", "messages"})
