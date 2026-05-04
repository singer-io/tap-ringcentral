import unittest

from singer import metadata

from tap_ringcentral.discover import discover

try:
    from .base import RingCentralBaseTest
except ImportError:
    from base import RingCentralBaseTest


class DiscoveryIntegrationTest(RingCentralBaseTest, unittest.TestCase):
    """Verify that ``discover()`` returns the correct catalogue for every
    available stream – including key properties and metadata."""

    def test_discovery_returns_all_expected_streams(self):
        catalog = discover()
        stream_map = {s.tap_stream_id: s for s in catalog.streams}
        expected_streams = self.expected_metadata()

        self.assertEqual(set(stream_map.keys()), set(expected_streams.keys()))

    def test_discovery_key_properties(self):
        catalog = discover()
        stream_map = {s.tap_stream_id: s for s in catalog.streams}
        expected_streams = self.expected_metadata()

        for stream_name, expected in expected_streams.items():
            with self.subTest(stream=stream_name):
                root_md = metadata.to_map(stream_map[stream_name].metadata)[()]
                actual_pks = set(root_md.get("table-key-properties", []))
                self.assertEqual(actual_pks, expected[self.PRIMARY_KEYS])

    def test_discovery_replication_metadata(self):
        catalog = discover()
        stream_map = {s.tap_stream_id: s for s in catalog.streams}
        expected_streams = self.expected_metadata()

        for stream_name, expected in expected_streams.items():
            with self.subTest(stream=stream_name):
                root_md = metadata.to_map(stream_map[stream_name].metadata)[()]
                actual_method = root_md.get("forced-replication-method")
                self.assertEqual(actual_method, expected[self.REPLICATION_METHOD])

                actual_rep_keys = root_md.get("valid-replication-keys", [])
                if isinstance(actual_rep_keys, str):
                    actual_rep_keys = {actual_rep_keys}
                else:
                    actual_rep_keys = set(actual_rep_keys)
                self.assertEqual(actual_rep_keys, expected[self.REPLICATION_KEYS])


if __name__ == "__main__":
    unittest.main()
