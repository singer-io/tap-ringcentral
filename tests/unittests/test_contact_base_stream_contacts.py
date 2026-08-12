import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytz

from tap_ringcentral.streams.base import ContactBaseStream


class TestContactBaseStreamSyncDataForPeriodWithContacts(unittest.TestCase):
    """
    Unit tests for ContactBaseStream.sync_data_for_period when contacts cache is populated.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        self.config = {
            "client_id": "test",
            "client_secret": "test",
            "refresh_token": "test",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        self.state = {}
        self.mock_catalog = MagicMock()
        self.mock_catalog.metadata = None
        self.mock_client = MagicMock()

    @patch("tap_ringcentral.streams.base.tap_ringcentral.cache.contacts")
    def test_sync_data_for_period_iterates_contacts(self, mock_cache_contacts):
        """Test sync_data_for_period iterates through cached contacts."""
        stream = ContactBaseStream(self.config, self.state, self.mock_catalog, self.mock_client)
        stream.TABLE = "call_log"

        # Mock cache with multiple contacts
        mock_cache_contacts.__iter__ = MagicMock(return_value=iter([
            {"id": "ext1"},
            {"id": "ext2"},
        ]))

        stream.sync_data_for_extension = MagicMock()

        date = datetime(2025, 1, 1, tzinfo=pytz.utc)
        interval = timedelta(days=7)

        stream.sync_data_for_period(date, interval)

        # Verify sync_data_for_extension was called for each contact
        self.assertEqual(stream.sync_data_for_extension.call_count, 2)

        # Verify it was called with correct extensionIds
        calls = stream.sync_data_for_extension.call_args_list
        self.assertEqual(calls[0][0][2], "ext1")
        self.assertEqual(calls[1][0][2], "ext2")
