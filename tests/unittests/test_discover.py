import unittest
from unittest.mock import patch, MagicMock
from singer.catalog import Catalog
from tap_ringcentral.discover import discover, _apply_access_checks, _prune_inaccessible_children
from tap_ringcentral.client import RingCentralForbiddenError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schemas(*stream_names):
    return {
        name: {"type": "object", "properties": {"id": {"type": "string"}}}
        for name in stream_names
    }


def _make_metadata(*stream_names):
    return {
        name: [{"breadcrumb": (), "metadata": {"table-key-properties": ["id"]}}]
        for name in stream_names
    }


ALL_STREAMS = ["contacts", "call_log", "company_call_log", "messages"]


# ---------------------------------------------------------------------------
# TestDiscover
# ---------------------------------------------------------------------------

class TestDiscover(unittest.TestCase):
    """Unit tests for the `discover` function."""

    @patch("tap_ringcentral.discover._apply_access_checks")
    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_returns_catalog(self, mock_get_schemas, _mock_access):
        """discover(client) returns a Catalog instance."""
        mock_get_schemas.return_value = (
            _make_schemas("contacts"),
            _make_metadata("contacts"),
        )
        catalog = discover(MagicMock())
        self.assertIsInstance(catalog, Catalog)

    @patch("tap_ringcentral.discover._apply_access_checks")
    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_has_expected_streams(self, mock_get_schemas, _mock_access):
        """discover(client) returns all four expected streams."""
        mock_get_schemas.return_value = (
            _make_schemas(*ALL_STREAMS),
            _make_metadata(*ALL_STREAMS),
        )
        catalog = discover(MagicMock())
        stream_names = [entry.stream for entry in catalog.streams]
        for name in ALL_STREAMS:
            self.assertIn(name, stream_names)
        self.assertEqual(len(catalog.streams), 4)

    @patch("tap_ringcentral.discover._apply_access_checks")
    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_stream_has_key_properties(self, mock_get_schemas, _mock_access):
        """Each stream entry carries the correct key_properties."""
        mock_get_schemas.return_value = (
            _make_schemas("contacts"),
            _make_metadata("contacts"),
        )
        catalog = discover(MagicMock())
        self.assertEqual(catalog.streams[0].key_properties, ["id"])

    @patch("tap_ringcentral.discover._apply_access_checks")
    @patch("tap_ringcentral.discover.get_schemas")
    def test_discover_with_client_calls_access_checks(
        self, mock_get_schemas, mock_apply_access
    ):
        """When a client is supplied, _apply_access_checks is called."""
        mock_get_schemas.return_value = (
            _make_schemas(*ALL_STREAMS),
            _make_metadata(*ALL_STREAMS),
        )
        mock_client = MagicMock()
        discover(mock_client)
        mock_apply_access.assert_called_once()
        args = mock_apply_access.call_args[0]
        self.assertIs(args[0], mock_client)


# ---------------------------------------------------------------------------
# TestApplyAccessChecks
# ---------------------------------------------------------------------------

class TestApplyAccessChecks(unittest.TestCase):
    """Unit tests for _apply_access_checks."""

    def _stream_mock(self, accessible):
        """Return a stream-class mock whose instantiation returns a check_access stub."""
        instance = MagicMock()
        instance.check_access.return_value = accessible
        cls = MagicMock(return_value=instance)
        cls.parent = None
        return cls

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_all_streams_accessible_catalog_unchanged(self, mock_streams):
        """When every stream is accessible, schemas and metadata are untouched."""
        mock_streams.__iter__ = lambda _: iter(ALL_STREAMS)
        mock_streams.items.return_value = [
            (n, self._stream_mock(True)) for n in ALL_STREAMS
        ]
        schemas = _make_schemas(*ALL_STREAMS)
        metadata = _make_metadata(*ALL_STREAMS)
        _apply_access_checks(MagicMock(), schemas, metadata)
        self.assertEqual(set(schemas.keys()), set(ALL_STREAMS))

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_inaccessible_stream_removed_from_catalog(self, mock_streams):
        """A stream returning check_access=False is removed from schemas/metadata."""
        stream_mocks = {
            "contacts": self._stream_mock(True),
            "call_log": self._stream_mock(False),
            "company_call_log": self._stream_mock(True),
            "messages": self._stream_mock(True),
        }
        mock_streams.items.return_value = list(stream_mocks.items())
        schemas = _make_schemas(*ALL_STREAMS)
        metadata = _make_metadata(*ALL_STREAMS)

        _apply_access_checks(MagicMock(), schemas, metadata)

        self.assertNotIn("call_log", schemas)
        self.assertNotIn("call_log", metadata)
        for name in ["contacts", "company_call_log", "messages"]:
            self.assertIn(name, schemas)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_all_inaccessible_raises_forbidden_error(self, mock_streams):
        """When every stream is inaccessible, RingCentralForbiddenError is raised."""
        mock_streams.items.return_value = [
            (n, self._stream_mock(False)) for n in ALL_STREAMS
        ]
        schemas = _make_schemas(*ALL_STREAMS)
        metadata = _make_metadata(*ALL_STREAMS)

        with self.assertRaises(RingCentralForbiddenError):
            _apply_access_checks(MagicMock(), schemas, metadata)


# ---------------------------------------------------------------------------
# TestPruneInaccessibleChildren
# ---------------------------------------------------------------------------

class TestPruneInaccessibleChildren(unittest.TestCase):
    """Unit tests for _prune_inaccessible_children."""

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_child_pruned_when_parent_missing(self, mock_streams):
        """A child stream is removed when its parent is absent from schemas."""
        parent_cls = MagicMock()
        parent_cls.parent = None
        child_cls = MagicMock()
        child_cls.parent = "parent_stream"

        mock_streams.items.return_value = [
            ("parent_stream", parent_cls),
            ("child_stream", child_cls),
        ]

        schemas = {"child_stream": {}}          # parent already removed
        metadata = {"child_stream": []}

        _prune_inaccessible_children(schemas, metadata)

        self.assertNotIn("child_stream", schemas)
        self.assertNotIn("child_stream", metadata)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_child_kept_when_parent_present(self, mock_streams):
        """A child stream is retained when its parent remains in schemas."""
        parent_cls = MagicMock()
        parent_cls.parent = None
        child_cls = MagicMock()
        child_cls.parent = "parent_stream"

        mock_streams.items.return_value = [
            ("parent_stream", parent_cls),
            ("child_stream", child_cls),
        ]

        schemas = {"parent_stream": {}, "child_stream": {}}
        metadata = {"parent_stream": [], "child_stream": []}

        _prune_inaccessible_children(schemas, metadata)

        self.assertIn("parent_stream", schemas)
        self.assertIn("child_stream", schemas)

    @patch("tap_ringcentral.discover.AVAILABLE_STREAMS")
    def test_no_parent_streams_at_all(self, mock_streams):
        """All independent streams (parent=None) are retained unchanged."""
        cls_a = MagicMock()
        cls_a.parent = None
        cls_b = MagicMock()
        cls_b.parent = None

        mock_streams.items.return_value = [("a", cls_a), ("b", cls_b)]
        schemas = {"a": {}, "b": {}}
        metadata = {"a": [], "b": []}

        _prune_inaccessible_children(schemas, metadata)

        self.assertEqual(set(schemas.keys()), {"a", "b"})


# ---------------------------------------------------------------------------
# TestGetSchemas
# ---------------------------------------------------------------------------

class TestGetSchemas(unittest.TestCase):
    """Unit tests for `get_schemas`."""

    @patch("tap_ringcentral.schema.open", create=True)
    @patch("tap_ringcentral.schema.json.load")
    def test_get_schemas_returns_all_streams(self, mock_json_load, mock_open):
        """get_schemas returns schemas for all available streams."""
        mock_json_load.return_value = {
            "type": "object",
            "properties": {"id": {"type": "string"}},
        }

        from tap_ringcentral.schema import get_schemas
        schemas, field_metadata = get_schemas()
        for name in ALL_STREAMS:
            self.assertIn(name, schemas)
            self.assertIn(name, field_metadata)
