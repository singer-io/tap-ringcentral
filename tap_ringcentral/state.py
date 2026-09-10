import json
import singer

from dateutil.parser import parse
from singer import write_bookmark, get_bookmark

LOGGER = singer.get_logger()


def migrate_bookmark_format(state, table, replication_key):
    """
    Migrate from old bookmark format to Singer standard format.

    Old format: state['bookmarks'][table]['last_record']
    New format: state['bookmarks'][table][replication_key]

    This function handles backward compatibility with existing state files.
    """
    old_bookmark = state.get('bookmarks', {}).get(table, {}).get('last_record')
    if old_bookmark:
        # Check if new format doesn't already exist
        if replication_key not in state.get('bookmarks', {}).get(table, {}):
            LOGGER.info('Migrating bookmark for %s from old format to Singer standard', table)
            state = write_bookmark(state, table, replication_key, old_bookmark)
            # Remove the stale key so state files don't accumulate dead entries
            state['bookmarks'][table].pop('last_record', None)

    return state


def get_last_record_value_for_table(state, table, replication_key='processedUntil'):
    """
    DEPRECATED: Use singer.get_bookmark() instead.

    Kept for backward compatibility. Returns parsed datetime from bookmark.
    Automatically migrates old state format if needed.
    """
    state = migrate_bookmark_format(state, table, replication_key)

    last_value = get_bookmark(
        state,
        table,
        key=replication_key,
        default=None
    )

    if last_value is None:
        return None

    return parse(last_value) if isinstance(last_value, str) else last_value


def incorporate(state, table, field, value, replication_key='processedUntil'):
    """
    DEPRECATED: Use singer.write_bookmark() instead.

    Kept for backward compatibility. Only advances bookmark if value is provided.
    """
    if value is None:
        return state

    # Migrate old format if needed
    state = migrate_bookmark_format(state, table, replication_key)

    # Only advance if the new value is greater than the current bookmark
    current = get_bookmark(state, table, key=replication_key, default=None)
    if current is not None and current >= value:
        return state

    return write_bookmark(state, table, replication_key, value)


def save_state(state):
    if not state:
        return

    LOGGER.info('Updating state.')

    singer.write_state(state)


def load_state(filename):
    if filename is None:
        return {}

    try:
        with open(filename) as handle:
            return json.load(handle)
    except:
        LOGGER.fatal("Failed to decode state file. Is it valid json?")
        raise RuntimeError
