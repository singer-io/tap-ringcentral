import unittest
from unittest.mock import patch, MagicMock

from tap_ringcentral.discover import discover, _apply_access_checks, _prune_inaccessible_children
from tap_ringcentral.client import RingCentralForbiddenError


class TestDiscover(unittest.TestCase):
    """
    Unit tests for the discover function.
    """

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_without_client(self, mock_get_schemas):
        """Test discover without client does not perform access checks."""
        mock_get_schemas.return_value = (
            {"contacts": {"type": "object", "properties": {}}},
            {"contacts": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}]}
        )

        catalog = discover(client=None)

        self.assertEqual(len(catalog.streams), 1)
        self.assertEqual(catalog.streams[0].stream, "contacts")
        mock_get_schemas.assert_called_once()

    @patch("tap_ringcentral.discover._apply_access_checks")
    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_with_client_applies_access_checks(self, mock_get_schemas, mock_apply_checks):
        """Test discover with client calls access checks."""
        mock_get_schemas.return_value = (
            {"contacts": {"type": "object", "properties": {}}},
            {"contacts": [{"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}]}
        )
        mock_client = MagicMock()

        catalog = discover(client=mock_client)

        mock_apply_checks.assert_called_once()
        self.assertEqual(len(catalog.streams), 1)

    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_returns_catalog_with_correct_properties(self, mock_get_schemas):
        """Test discover returns catalog with correct stream properties."""
        mock_get_schemas.return_value = (
            {
                "contacts": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "name": {"type": "string"}}
                }
            },
            {
                "contacts": [
                    {"breadcrumb": [], "metadata": {"table-key-properties": ["id"]}}
                ]
            }
        )

        catalog = discover(client=None)

        self.assertEqual(len(catalog.streams), 1)
        stream = catalog.streams[0]
        self.assertEqual(stream.stream, "contacts")
        self.assertEqual(stream.tap_stream_id, "contacts")
        self.assertEqual(stream.key_properties, ["id"])


class TestApplyAccessChecks(unittest.TestCase):
    """
    Unit tests for the _apply_access_checks function.
    """

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_all_streams_accessible_catalog_unchanged(self, mock_available_streams):
        """Test _apply_access_checks does not modify catalog when all streams are accessible."""
        mock_stream_class = MagicMock()
        # Ensure the mock class doesn't have a parent attribute
        del mock_stream_class.parent

        mock_stream_instance = MagicMock()
        mock_stream_instance.check_access.return_value = True
        mock_stream_class.return_value = mock_stream_instance

        mock_available_streams.items.return_value = [("contacts", mock_stream_class)]

        schemas = {"contacts": {}}
        field_metadata = {"contacts": []}

        mock_client = MagicMock()

        # Should not raise any exception
        _apply_access_checks(mock_client, schemas, field_metadata)

        self.assertIn("contacts", schemas)
        self.assertIn("contacts", field_metadata)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_inaccessible_stream_removed_from_catalog(self, mock_available_streams):
        """Test _apply_access_checks removes inaccessible streams."""
        mock_stream_class = MagicMock()
        mock_stream_instance = MagicMock()
        mock_stream_instance.check_access.return_value = False
        mock_stream_class.return_value = mock_stream_instance

        mock_available_streams.items.return_value = [
            ("contacts", mock_stream_class),
            ("call_log", mock_stream_class)
        ]

        schemas = {"contacts": {}, "call_log": {}}
        field_metadata = {"contacts": [], "call_log": []}

        mock_client = MagicMock()

        with self.assertRaises(RingCentralForbiddenError):
            _apply_access_checks(mock_client, schemas, field_metadata)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_all_inaccessible_raises_forbidden_error(self, mock_available_streams):
        """Test _apply_access_checks raises error when all streams are inaccessible."""
        mock_stream_class = MagicMock()
        mock_stream_instance = MagicMock()
        mock_stream_instance.check_access.return_value = False
        mock_stream_class.return_value = mock_stream_instance

        mock_available_streams.items.return_value = [("contacts", mock_stream_class)]

        schemas = {"contacts": {}}
        field_metadata = {"contacts": []}

        mock_client = MagicMock()

        with self.assertRaises(RingCentralForbiddenError) as context:
            _apply_access_checks(mock_client, schemas, field_metadata)

        self.assertIn("403", str(context.exception))


class TestPruneInaccessibleChildren(unittest.TestCase):
    """
    Unit tests for the _prune_inaccessible_children function.
    """

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_child_pruned_when_parent_missing(self, mock_available_streams):
        """Test child stream is removed when parent stream is not in schemas."""
        # Create a mock child stream class with parent attribute
        mock_child_class = MagicMock()
        mock_child_class.parent = "contacts"

        # Create a mock parent stream class without parent attribute
        mock_parent_class = MagicMock()
        del mock_parent_class.parent

        mock_available_streams.items.return_value = [
            ("contacts", mock_parent_class),
            ("call_log", mock_child_class),
        ]

        schemas = {"call_log": {}}  # Parent "contacts" is missing
        field_metadata = {"call_log": []}

        _prune_inaccessible_children(schemas, field_metadata)

        self.assertNotIn("call_log", schemas)
        self.assertNotIn("call_log", field_metadata)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_child_kept_when_parent_present(self, mock_available_streams):
        """Test child stream is kept when parent stream is in schemas."""
        mock_child_class = MagicMock()
        mock_child_class.parent = "contacts"

        mock_parent_class = MagicMock()
        del mock_parent_class.parent

        mock_available_streams.items.return_value = [
            ("contacts", mock_parent_class),
            ("call_log", mock_child_class),
        ]

        schemas = {"contacts": {}, "call_log": {}}
        field_metadata = {"contacts": [], "call_log": []}

        _prune_inaccessible_children(schemas, field_metadata)

        self.assertIn("call_log", schemas)
        self.assertIn("call_log", field_metadata)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_no_parent_streams_at_all(self, mock_available_streams):
        """Test function handles case where no streams have parents."""
        mock_parent_class = MagicMock()
        del mock_parent_class.parent

        mock_available_streams.items.return_value = [
            ("contacts", mock_parent_class),
            ("messages", mock_parent_class),
        ]

        schemas = {"contacts": {}, "messages": {}}
        field_metadata = {"contacts": [], "messages": []}

        _prune_inaccessible_children(schemas, field_metadata)

        self.assertIn("contacts", schemas)
        self.assertIn("messages", schemas)
