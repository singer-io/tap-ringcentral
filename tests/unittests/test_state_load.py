import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os

from tap_ringcentral.state import load_state


class TestLoadState(unittest.TestCase):
    """
    Unit tests for the load_state function in tap_ringcentral/state.py
    """

    def test_load_state_with_none_filename(self):
        """Test that load_state returns empty dict when filename is None."""
        result = load_state(None)
        self.assertEqual(result, {})

    @patch("builtins.open", new_callable=mock_open, read_data='{"bookmarks": {"contacts": {"last_record": "2025-01-01T00:00:00Z"}}}')
    def test_load_state_with_valid_file(self, mock_file):
        """Test that load_state loads and returns state from valid JSON file."""
        result = load_state("/path/to/state.json")
        self.assertIn("bookmarks", result)
        self.assertIn("contacts", result["bookmarks"])
        mock_file.assert_called_once_with("/path/to/state.json")

    @patch("builtins.open", new_callable=mock_open, read_data='{}')
    def test_load_state_with_empty_json(self, mock_file):
        """Test that load_state returns empty dict from empty JSON file."""
        result = load_state("/path/to/state.json")
        self.assertEqual(result, {})

    @patch("builtins.open", new_callable=mock_open)
    def test_load_state_with_invalid_json(self, mock_file):
        """Test that load_state raises RuntimeError on invalid JSON."""
        mock_file.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        with self.assertRaises(RuntimeError):
            load_state("/path/to/invalid.json")

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_state_with_nonexistent_file(self, mock_file):
        """Test that load_state raises RuntimeError when file does not exist."""
        with self.assertRaises(RuntimeError):
            load_state("/path/to/nonexistent.json")

    @patch("builtins.open", new_callable=mock_open, read_data='{"bookmarks": {"contacts": {"field": "last_record", "last_record": "2025-01-01T00:00:00Z"}, "messages": {"field": "last_record", "last_record": "2025-01-02T00:00:00Z"}}}')
    def test_load_state_with_multiple_bookmarks(self, mock_file):
        """Test that load_state correctly loads multiple bookmarks."""
        result = load_state("/path/to/state.json")
        self.assertEqual(len(result["bookmarks"]), 2)
        self.assertIn("contacts", result["bookmarks"])
        self.assertIn("messages", result["bookmarks"])

    @patch("builtins.open", new_callable=mock_open, read_data='{"bookmarks": {}, "other_key": "other_value"}')
    def test_load_state_preserves_additional_keys(self, mock_file):
        """Test that load_state preserves additional keys in state."""
        result = load_state("/path/to/state.json")
        self.assertIn("other_key", result)
        self.assertEqual(result["other_key"], "other_value")
