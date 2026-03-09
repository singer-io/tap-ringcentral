import unittest
from tap_ringcentral.state import incorporate, get_last_record_value_for_table, save_state, load_state
from unittest.mock import patch, MagicMock
from dateutil.parser import parse


class TestIncorporate(unittest.TestCase):
    """
    Unit tests for the `incorporate` function in the tap_ringcentral.state module.

    This test class verifies that:
      - State is correctly updated with new bookmark values.
      - None values do not modify state.
      - Newer values replace older bookmarks.
      - Older values do not overwrite newer bookmarks.
    """

    def test_incorporate_creates_new_bookmark(self):
        """Test that incorporate creates a new bookmark entry in state."""
        state = {}
        new_state = incorporate(state, "contacts", "last_record", "2025-01-15T00:00:00Z")
        self.assertIn("bookmarks", new_state)
        self.assertIn("contacts", new_state["bookmarks"])
        self.assertEqual(new_state["bookmarks"]["contacts"]["last_record"], "2025-01-15T00:00:00Z")
        self.assertEqual(new_state["bookmarks"]["contacts"]["field"], "last_record")

    def test_incorporate_none_value_returns_state_unchanged(self):
        """Test that incorporate with None value returns state unchanged."""
        state = {"bookmarks": {"contacts": {"last_record": "2025-01-01T00:00:00Z"}}}
        new_state = incorporate(state, "contacts", "last_record", None)
        self.assertEqual(new_state, state)

    def test_incorporate_newer_value_updates_bookmark(self):
        """Test that a newer value replaces an older bookmark."""
        state = {"bookmarks": {"contacts": {"field": "last_record", "last_record": "2025-01-01T00:00:00Z"}}}
        new_state = incorporate(state, "contacts", "last_record", "2025-02-01T00:00:00Z")
        self.assertEqual(new_state["bookmarks"]["contacts"]["last_record"], "2025-02-01T00:00:00Z")

    def test_incorporate_older_value_does_not_update_bookmark(self):
        """Test that an older value does not overwrite a newer bookmark."""
        state = {"bookmarks": {"contacts": {"field": "last_record", "last_record": "2025-02-01T00:00:00Z"}}}
        new_state = incorporate(state, "contacts", "last_record", "2025-01-01T00:00:00Z")
        self.assertEqual(new_state["bookmarks"]["contacts"]["last_record"], "2025-02-01T00:00:00Z")


class TestGetLastRecordValueForTable(unittest.TestCase):
    """
    Unit tests for the `get_last_record_value_for_table` function.
    """

    def test_returns_none_when_no_bookmarks(self):
        """Test returns None when there are no bookmarks."""
        state = {}
        result = get_last_record_value_for_table(state, "contacts")
        self.assertIsNone(result)

    def test_returns_none_when_table_not_in_bookmarks(self):
        """Test returns None when table is not in bookmarks."""
        state = {"bookmarks": {"other_table": {"last_record": "2025-01-01T00:00:00Z"}}}
        result = get_last_record_value_for_table(state, "contacts")
        self.assertIsNone(result)

    def test_returns_parsed_date_when_bookmark_exists(self):
        """Test returns a parsed datetime when a valid bookmark exists."""
        state = {"bookmarks": {"contacts": {"last_record": "2025-01-15T00:00:00Z"}}}
        result = get_last_record_value_for_table(state, "contacts")
        expected = parse("2025-01-15T00:00:00Z")
        self.assertEqual(result, expected)


class TestSaveState(unittest.TestCase):
    """
    Unit tests for the `save_state` function.
    """

    @patch("tap_ringcentral.state.singer.write_state")
    def test_save_state_writes_state(self, mock_write_state):
        """Test that save_state calls singer.write_state with the state."""
        state = {"bookmarks": {"contacts": {"last_record": "2025-01-01T00:00:00Z"}}}
        save_state(state)
        mock_write_state.assert_called_once_with(state)

    @patch("tap_ringcentral.state.singer.write_state")
    def test_save_state_does_nothing_for_empty_state(self, mock_write_state):
        """Test that save_state does nothing when state is empty."""
        save_state({})
        mock_write_state.assert_not_called()

    @patch("tap_ringcentral.state.singer.write_state")
    def test_save_state_does_nothing_for_none(self, mock_write_state):
        """Test that save_state does nothing when state is None."""
        save_state(None)
        mock_write_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
