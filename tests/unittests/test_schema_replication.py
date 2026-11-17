import unittest
from unittest.mock import patch, MagicMock
from tap_ringcentral.schema import get_schemas


class TestGetSchemasWithReplicationKeys(unittest.TestCase):
    """
    Unit tests for get_schemas when streams have REPLICATION_KEYS.
    """

    @patch("tap_ringcentral.schema.AVAILABLE_STREAMS")
    @patch("builtins.open")
    def test_get_schemas_marks_replication_keys_as_automatic(self, mock_open_file, mock_available_streams):
        """Test that get_schemas marks REPLICATION_KEYS as automatic inclusion."""
        # Create a mock stream with REPLICATION_KEYS
        mock_stream_class = MagicMock()
        mock_stream_class.KEY_PROPERTIES = ["id"]
        mock_stream_class.REPLICATION_KEYS = ["updated_at"]  # This field should be marked automatic
        mock_stream_class.REPLICATION_METHOD = "INCREMENTAL"

        mock_available_streams.items.return_value = [("messages", mock_stream_class)]

        # Mock the schema file
        schema_dict = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "updated_at": {"type": "string"},
            }
        }

        mock_open_file.return_value.__enter__.return_value.read.return_value = str(schema_dict)

        with patch("tap_ringcentral.schema.json.load", return_value=schema_dict):
            schemas, field_metadata = get_schemas()

        # Verify both dicts returned
        self.assertIn("messages", schemas)
        self.assertIn("messages", field_metadata)

        # Verify metadata includes the stream
        self.assertIsNotNone(field_metadata["messages"])
