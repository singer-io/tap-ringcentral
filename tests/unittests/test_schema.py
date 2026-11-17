import unittest
from unittest.mock import patch, MagicMock
from tap_ringcentral.schema import get_schemas, get_abs_path
import os
import json


class TestGetAbsPath(unittest.TestCase):
    """
    Unit tests for the get_abs_path function in tap_ringcentral/schema.py
    """

    def test_get_abs_path_returns_absolute_path(self):
        """Test that get_abs_path returns an absolute path."""
        result = get_abs_path("schemas/contacts.json")
        self.assertTrue(os.path.isabs(result))

    def test_get_abs_path_contains_schema_directory(self):
        """Test that get_abs_path includes the schema directory."""
        result = get_abs_path("schemas/contacts.json")
        self.assertIn("schemas/contacts.json", result)

    def test_get_abs_path_with_different_files(self):
        """Test that get_abs_path works with different file names."""
        path1 = get_abs_path("schemas/contacts.json")
        path2 = get_abs_path("schemas/call_log.json")
        self.assertNotEqual(path1, path2)
        self.assertIn("contacts.json", path1)
        self.assertIn("call_log.json", path2)


class TestGetSchemas(unittest.TestCase):
    """
    Unit tests for the get_schemas function in tap_ringcentral/schema.py
    """

    def test_get_schemas_returns_two_dicts(self):
        """Test that get_schemas returns two dictionaries."""
        schemas, field_metadata = get_schemas()
        self.assertIsInstance(schemas, dict)
        self.assertIsInstance(field_metadata, dict)

    def test_get_schemas_schemas_not_empty(self):
        """Test that returned schemas dictionary is not empty."""
        schemas, field_metadata = get_schemas()
        self.assertGreater(len(schemas), 0)

    def test_get_schemas_field_metadata_not_empty(self):
        """Test that returned field_metadata dictionary is not empty."""
        schemas, field_metadata = get_schemas()
        self.assertGreater(len(field_metadata), 0)

    def test_get_schemas_same_keys(self):
        """Test that schemas and field_metadata have the same keys."""
        schemas, field_metadata = get_schemas()
        self.assertEqual(set(schemas.keys()), set(field_metadata.keys()))

    def test_get_schemas_contains_expected_streams(self):
        """Test that schemas includes expected stream names."""
        schemas, field_metadata = get_schemas()
        expected_streams = ["call_log", "company_call_log", "contacts", "messages"]
        for stream in expected_streams:
            self.assertIn(stream, schemas)

    def test_get_schemas_schema_has_properties(self):
        """Test that each schema has a properties key."""
        schemas, field_metadata = get_schemas()
        for stream_name, schema in schemas.items():
            self.assertIn("properties", schema, f"Schema for {stream_name} missing properties")

    def test_get_schemas_field_metadata_is_list(self):
        """Test that field_metadata values are lists."""
        schemas, field_metadata = get_schemas()
        for stream_name, mdata in field_metadata.items():
            self.assertIsInstance(mdata, list, f"Metadata for {stream_name} is not a list")

    def test_get_schemas_metadata_has_table_key_properties(self):
        """Test that metadata includes table-key-properties."""
        from singer.metadata import to_map
        schemas, field_metadata = get_schemas()
        for stream_name, mdata in field_metadata.items():
            mdata_map = to_map(mdata)
            self.assertIn((), mdata_map)
            self.assertIn("table-key-properties", mdata_map[()])
