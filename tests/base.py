import os
import json
from tap_ringcentral.schema import get_schemas


class RingCentralBaseTest:
    """Base class for RingCentral integration tests.

    Provides common config, state, expected metadata, and schema-driven
    mock-record generation – mirroring the pattern used by
    tap-referral-saasquatch's integration test suite.
    """

    default_start_date = "2025-01-01T00:00:00Z"
    PRIMARY_KEYS = "primary_keys"
    REPLICATION_METHOD = "replication_method"
    REPLICATION_KEYS = "replication_keys"
    OBEYS_START_DATE = "obeys_start_date"

    # Reusable dummy config – no real credentials are needed because the
    # RingCentralClient is always mocked in integration tests.
    DEFAULT_CONFIG = {
        "client_id": "dummy-client-id",
        "client_secret": "dummy-client-secret",
        "refresh_token": "dummy-refresh-token",
        "api_url": "https://platform.ringcentral.com",
        "start_date": "2025-01-01T00:00:00Z",
        "user_agent": "tap-ringcentral-test",
    }

    @classmethod
    def expected_metadata(cls):
        """Return a dict of stream-name → expected catalogue properties.

        contacts uses BaseStream (FULL_TABLE, single page listing).
        call_log, company_call_log and messages use ContactBaseStream
        (INCREMENTAL, 7-day windowed sync) but the tap currently does NOT
        declare REPLICATION_METHOD/REPLICATION_KEYS on the stream classes,
        so the metadata reflects that.
        """
        return {
            "contacts": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: "FULL_TABLE",
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: False,
            },
            "call_log": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: None,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: True,
            },
            "company_call_log": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: None,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: True,
            },
            "messages": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: None,
                cls.REPLICATION_KEYS: set(),
                cls.OBEYS_START_DATE: True,
            },
        }

    # ------------------------------------------------------------------
    # Schema-driven mock value generators
    # ------------------------------------------------------------------

    @staticmethod
    def _schema_type(schema):
        """Return the concrete type for a JSON-schema fragment, unwinding
        nullable union types like ``["null", "string"]``."""
        schema_type = schema.get("type", "object")
        if isinstance(schema_type, list):
            non_null = [t for t in schema_type if t != "null"]
            return non_null[0] if non_null else "null"
        return schema_type

    @staticmethod
    def _generate_value(schema, date_value="2024-01-01T00:00:00Z"):
        """Produce one valid mock value for an arbitrary JSON-schema node."""
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

        # Properties with no type are treated as a pass-through (e.g. ``"deleted": {}``)
        if not schema:
            return None

        schema_type = RingCentralBaseTest._schema_type(schema)

        if schema_type == "object":
            properties = schema.get("properties", {})
            return {
                key: RingCentralBaseTest._generate_value(val, date_value=date_value)
                for key, val in properties.items()
            }
        if schema_type == "array":
            return [
                RingCentralBaseTest._generate_value(
                    schema.get("items", {"type": "string"}),
                    date_value=date_value,
                )
            ]
        if schema_type == "string":
            fmt = schema.get("format")
            if fmt == "date-time":
                return date_value
            if fmt == "email":
                return "mock@example.com"
            return "mock"
        if schema_type == "integer":
            return 1
        if schema_type == "number":
            return 1.0
        if schema_type == "boolean":
            return True
        # Untyped fields (``{}``) – return None
        return None

    @staticmethod
    def _generate_stream_record(stream_name, date_value="2024-01-01T00:00:00Z"):
        """Generate a single schema-conformant record for *stream_name*."""
        schemas, _ = get_schemas()
        return RingCentralBaseTest._generate_value(
            schemas[stream_name], date_value=date_value
        )

    # ------------------------------------------------------------------
    # Convenience helpers for building mock API responses
    # ------------------------------------------------------------------

    @staticmethod
    def make_contacts_api_response(records, page=1, total_pages=1):
        """Build a mock response dict that ``BaseStream.sync_data`` expects
        when fetching the ``/directory/entries`` endpoint."""
        return {
            "records": records,
            "paging": {
                "page": page,
                "totalPages": total_pages,
                "perPage": 1000,
            },
        }

    @staticmethod
    def make_call_log_api_response(records):
        """Build a mock response dict that ``ContactBaseStream`` expects."""
        return {"records": records}
