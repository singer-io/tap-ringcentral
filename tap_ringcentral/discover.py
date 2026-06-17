import singer
from singer import metadata
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_ringcentral.client import RingCentralForbiddenError
from tap_ringcentral.schema import get_schemas
from tap_ringcentral.streams import AVAILABLE_STREAMS

LOGGER = singer.get_logger()


def _prune_inaccessible_children(schemas: dict, field_metadata: dict) -> None:
    """
    Remove child streams from the catalog whose parent stream was excluded.
    Mutates schemas and field_metadata in place.
    """
    for name, stream_cls in list(AVAILABLE_STREAMS.items()):
        parent = getattr(stream_cls, "parent", None)
        if name in schemas and parent and parent not in schemas:
            LOGGER.warning(
                "Stream '%s' excluded from catalog because its parent stream '%s' is not accessible.",
                name,
                parent,
            )
            schemas.pop(name, None)
            field_metadata.pop(name, None)


def _apply_access_checks(client, schemas: dict, field_metadata: dict) -> None:
    """
    Probe each stream for read access and remove inaccessible streams
    (and their children) from schemas and field_metadata in place.
    Raises RingCentralForbiddenError if no streams are accessible.
    """

    inaccessible_streams = [
        stream_name
        for stream_name, stream_obj in AVAILABLE_STREAMS.items()
        if stream_name in schemas
        and not stream_obj(client=client).check_access()
    ]

    for stream_name in inaccessible_streams:
        schemas.pop(stream_name, None)
        field_metadata.pop(stream_name, None)

    _prune_inaccessible_children(schemas, field_metadata)

    if not schemas:
        raise RingCentralForbiddenError(
            "HTTP-error-code: 403, Error: The credentials do not have 'read' access to any supported streams. Please re-check configuration."
        )
    if inaccessible_streams:
        LOGGER.warning(
            "No 'read' access to stream(s): %s. Excluded from catalog.",
            ", ".join(inaccessible_streams),
        )


def discover(client=None) -> Catalog:
    """Run discovery and return a catalog.

    Access to each stream is verified when a client is provided; streams
    that cannot be read are excluded from the returned catalog.
    """
    schemas, field_metadata = get_schemas()
    if client:  # Added client check since mock-integration tests are tightly dependent on discover call w/o client
        _apply_access_checks(client, schemas, field_metadata)

    catalog = Catalog([])
    for stream_name, schema_dict in schemas.items():
        try:
            schema = Schema.from_dict(schema_dict)
            mdata = field_metadata[stream_name]
        except Exception as err:
            LOGGER.error(err)
            LOGGER.error(f"stream_name: {stream_name}")
            LOGGER.error(f"type schema_dict: {type(schema_dict)}")
            raise err
        key_properties = metadata.to_map(mdata).get((), {}).get("table-key-properties")
        catalog.streams.append(
            CatalogEntry(
                stream=stream_name,
                tap_stream_id=stream_name,
                key_properties=key_properties,
                schema=schema,
                metadata=mdata,
            )
        )
    return catalog
