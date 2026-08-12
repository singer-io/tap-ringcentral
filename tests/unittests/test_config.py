import unittest
from tap_ringcentral.config import get_config_start_date
from dateutil.parser import parse


class TestGetConfigStartDate(unittest.TestCase):
    """
    Unit tests for the get_config_start_date function in tap_ringcentral/config.py
    """

    def test_get_config_start_date_with_iso_string(self):
        """Test that get_config_start_date parses ISO format strings."""
        config = {"start_date": "2025-01-15T00:00:00Z"}
        result = get_config_start_date(config)
        expected = parse("2025-01-15T00:00:00Z")
        self.assertEqual(result, expected)

    def test_get_config_start_date_with_different_format(self):
        """Test that get_config_start_date can parse various date formats."""
        config = {"start_date": "2025-01-15"}
        result = get_config_start_date(config)
        # Should parse without error
        self.assertIsNotNone(result)

    def test_get_config_start_date_returns_datetime_object(self):
        """Test that get_config_start_date returns a datetime object."""
        config = {"start_date": "2025-01-15T00:00:00Z"}
        result = get_config_start_date(config)
        self.assertTrue(hasattr(result, 'year'))
        self.assertTrue(hasattr(result, 'month'))
        self.assertTrue(hasattr(result, 'day'))

    def test_get_config_start_date_with_timezone(self):
        """Test that get_config_start_date preserves timezone info."""
        config = {"start_date": "2025-01-15T12:30:00-05:00"}
        result = get_config_start_date(config)
        self.assertIsNotNone(result.tzinfo)
