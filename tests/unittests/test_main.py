import unittest
from unittest.mock import patch, MagicMock, call
import sys
from io import StringIO

from tap_ringcentral import RingCentralRunner, main


class TestRingCentralRunner(unittest.TestCase):
    """
    Unit tests for the RingCentralRunner class in tap_ringcentral/__init__.py
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

        self.mock_client = MagicMock()
        self.mock_args = MagicMock()
        self.mock_args.config = self.config
        self.mock_args.state = self.state
        self.mock_args.catalog = MagicMock()
        self.mock_args.discover = False
        self.mock_args.catalog = False

    def test_runner_init(self):
        """Test that RingCentralRunner initializes correctly."""
        runner = RingCentralRunner(self.mock_args, self.mock_client)
        self.assertEqual(runner.config, self.config)
        self.assertEqual(runner.state, self.state)
        self.assertEqual(runner.catalog, self.mock_args.catalog)
        self.assertEqual(runner.client, self.mock_client)
        self.assertIsNotNone(runner.available_streams)

    @patch("tap_ringcentral.singer.write_state")
    def test_save_state_with_valid_state(self, mock_write_state):
        """Test that save_state writes state when state is provided."""
        runner = RingCentralRunner(self.mock_args, self.mock_client)
        state = {"bookmarks": {"contacts": {"last_record": "2025-01-01T00:00:00Z"}}}
        runner.save_state(state)
        mock_write_state.assert_called_once_with(state)

    @patch("tap_ringcentral.singer.write_state")
    def test_save_state_with_none_state(self, mock_write_state):
        """Test that save_state does nothing when state is None."""
        runner = RingCentralRunner(self.mock_args, self.mock_client)
        runner.save_state(None)
        mock_write_state.assert_not_called()

    @patch("tap_ringcentral.singer.write_state")
    def test_save_state_with_empty_state(self, mock_write_state):
        """Test that save_state does nothing when state is empty."""
        runner = RingCentralRunner(self.mock_args, self.mock_client)
        runner.save_state({})
        mock_write_state.assert_not_called()

    @patch("tap_ringcentral.json.dump")
    @patch("tap_ringcentral.discover")
    def test_do_discover(self, mock_discover, mock_json_dump):
        """Test that do_discover calls discover and outputs catalog."""
        mock_catalog = MagicMock()
        mock_catalog.to_dict.return_value = {"streams": []}
        mock_discover.return_value = mock_catalog

        runner = RingCentralRunner(self.mock_args, self.mock_client)
        runner.do_discover()

        mock_discover.assert_called_once_with(self.mock_client)
        mock_json_dump.assert_called_once()

    def test_do_sync_with_no_selected_streams(self):
        """Test do_sync when catalog has no selected streams."""
        self.mock_args.catalog = MagicMock()
        self.mock_args.catalog.get_selected_streams.return_value = []

        runner = RingCentralRunner(self.mock_args, self.mock_client)
        runner.do_sync()

        # Should not raise any exception
        self.mock_args.catalog.get_selected_streams.assert_called_once_with(self.state)

    def test_do_sync_with_selected_streams(self):
        """Test do_sync syncs selected streams."""
        # Setup mock stream
        mock_stream_obj = MagicMock()
        mock_stream_obj.TABLE = "test_stream"
        mock_stream_obj.state = self.state
        mock_stream_obj.sync.return_value = None

        # Setup mock catalog
        mock_catalog_entry = MagicMock()
        mock_catalog_entry.stream = "test_stream"

        self.mock_args.catalog = MagicMock()
        self.mock_args.catalog.get_selected_streams.return_value = [mock_catalog_entry]

        # Mock the stream class
        with patch.dict("tap_ringcentral.AVAILABLE_STREAMS", {"test_stream": MagicMock(return_value=mock_stream_obj)}):
            runner = RingCentralRunner(self.mock_args, self.mock_client)
            runner.do_sync()

            mock_stream_obj.sync.assert_called_once()

    def test_do_sync_with_stream_exception(self):
        """Test do_sync raises exception when stream sync fails."""
        # Setup mock stream that raises exception
        mock_stream_obj = MagicMock()
        mock_stream_obj.TABLE = "test_stream"
        mock_stream_obj.state = self.state
        mock_stream_obj.sync.side_effect = Exception("Sync failed")

        # Setup mock catalog
        mock_catalog_entry = MagicMock()
        mock_catalog_entry.stream = "test_stream"

        self.mock_args.catalog = MagicMock()
        self.mock_args.catalog.get_selected_streams.return_value = [mock_catalog_entry]

        # Mock the stream class
        with patch.dict("tap_ringcentral.AVAILABLE_STREAMS", {"test_stream": MagicMock(return_value=mock_stream_obj)}):
            runner = RingCentralRunner(self.mock_args, self.mock_client)
            with self.assertRaises(Exception):
                runner.do_sync()


class TestMainFunction(unittest.TestCase):
    """
    Unit tests for the main function in tap_ringcentral/__init__.py
    """

    @patch("tap_ringcentral.RingCentralRunner")
    @patch("tap_ringcentral.RingCentralClient")
    @patch("tap_ringcentral.singer.utils.parse_args")
    def test_main_discover_mode(self, mock_parse_args, mock_client_class, mock_runner_class):
        """Test main function in discover mode."""
        mock_args = MagicMock()
        mock_args.config = {"client_id": "test"}
        mock_args.config_path = "/path/to/config"
        mock_args.discover = True
        mock_args.catalog = None
        mock_parse_args.return_value = mock_args

        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        main()

        mock_parse_args.assert_called_once()
        mock_client_class.assert_called_once_with(mock_args.config, mock_args.config_path)
        mock_runner_class.assert_called_once()
        mock_runner.do_discover.assert_called_once()
        mock_runner.do_sync.assert_not_called()

    @patch("tap_ringcentral.RingCentralRunner")
    @patch("tap_ringcentral.RingCentralClient")
    @patch("tap_ringcentral.singer.utils.parse_args")
    def test_main_sync_mode(self, mock_parse_args, mock_client_class, mock_runner_class):
        """Test main function in sync mode."""
        mock_args = MagicMock()
        mock_args.config = {"client_id": "test"}
        mock_args.config_path = "/path/to/config"
        mock_args.discover = False
        mock_args.catalog = MagicMock()
        mock_parse_args.return_value = mock_args

        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        main()

        mock_parse_args.assert_called_once()
        mock_runner.do_sync.assert_called_once()
        mock_runner.do_discover.assert_not_called()

    @patch("tap_ringcentral.RingCentralRunner")
    @patch("tap_ringcentral.RingCentralClient")
    @patch("tap_ringcentral.singer.utils.parse_args")
    def test_main_neither_discover_nor_sync(self, mock_parse_args, mock_client_class, mock_runner_class):
        """Test main function when neither discover nor sync is specified."""
        mock_args = MagicMock()
        mock_args.config = {"client_id": "test"}
        mock_args.config_path = "/path/to/config"
        mock_args.discover = False
        mock_args.catalog = None  # No catalog provided
        mock_parse_args.return_value = mock_args

        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        main()

        # Neither should be called
        mock_runner.do_discover.assert_not_called()
        mock_runner.do_sync.assert_not_called()
