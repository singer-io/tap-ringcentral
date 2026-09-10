#!/usr/bin/env python3

import singer
import sys

import argparse
import json

from tap_ringcentral.discover import discover

import tap_ringcentral.cache
from tap_ringcentral.client import RingCentralClient, RingCentralForbiddenError
from tap_ringcentral.streams import AVAILABLE_STREAMS
from tap_ringcentral.streams.contacts import ContactsStream

LOGGER = singer.get_logger()  # noqa


class RingCentralRunner:
    def __init__(self, args, client):
        self.config = args.config
        self.state = args.state
        self.catalog = args.catalog
        self.client = client
        self.available_streams = AVAILABLE_STREAMS

    def save_state(self, state):
        if not state:
            return
        LOGGER.info('Updating state.')
        singer.write_state(state)

    def do_discover(self):
        LOGGER.info("Starting discovery")
        catalog = discover(self.client)
        json.dump(catalog.to_dict(), sys.stdout, indent=2)
        LOGGER.info("Finished discover")

    def _prefill_contacts_cache(self):
        """Fill contacts cache before sync if any selected stream requires it.

        Returns False if a required contacts fetch failed, so the caller
        can skip dependent streams instead of silently syncing zero records.
        """
        selected = {s.stream for s in self.catalog.get_selected_streams(self.state)}
        needs_contacts = any(
            'contacts' in getattr(self.available_streams.get(name), 'REQUIRES', [])
            for name in selected
        )

        # Skip pre-fill if contacts is selected — its own sync will fill the cache first
        if needs_contacts and 'contacts' not in selected and not tap_ringcentral.cache.contacts:
            LOGGER.info('Pre-filling contacts cache for extension-based streams')
            try:
                ContactsStream(self.config, self.state, None, self.client).fill_cache()
            except RingCentralForbiddenError as exc:
                LOGGER.error(
                    'Could not pre-fill contacts cache: %s. '
                    'Streams that depend on contacts will be skipped this run.',
                    str(exc)
                )
                return False
            LOGGER.info('Contacts cache filled with %d extensions', len(tap_ringcentral.cache.contacts))

        return True

    # Sync the streams in the order specified in the
    # streams/__init__.py list of AVAILABLE_STREAMS
    def do_sync(self):
        LOGGER.info("Starting sync.")
        contacts_available = self._prefill_contacts_cache()

        selected = self.catalog.get_selected_streams(self.state)

        # Ensure streams that others depend on sync first regardless of catalog order
        def _sync_order(entry):
            """Determine the sync order based on dependencies.

            Streams that are required by others should sync first.
            Returns a tuple where the first element indicates priority.

            Eg:
                (0, 'contacts') means this stream has no dependencies and should sync early.
                (1, 'messages') means this stream has dependencies and should sync later.
            """
            cls = self.available_streams.get(entry.stream)
            requires = getattr(cls, 'REQUIRES', []) if cls else []
            return (1 if requires else 0, entry.stream)

        selected = sorted(selected, key=_sync_order)

        for stream_to_sync in selected:
            stream_name = stream_to_sync.stream
            stream_cls = self.available_streams[stream_name]

            if not contacts_available and 'contacts' in getattr(stream_cls, 'REQUIRES', []):
                LOGGER.error(
                    'Skipping stream %s: requires contacts, which failed to load this run.',
                    stream_name
                )
                continue

            # Track currently syncing stream
            singer.set_currently_syncing(self.state, stream_name)
            singer.write_state(self.state)
            LOGGER.info('Currently syncing: %s', stream_name)

            stream_obj = stream_cls(
                        self.config, self.state, stream_to_sync, self.client
                    )
            try:
                stream_obj.state = self.state
                stream_obj.sync()
                self.state = stream_obj.state

                # Clear currently_syncing after successful sync
                singer.set_currently_syncing(self.state, None)
                singer.write_state(self.state)
            except Exception as e:
                LOGGER.error(str(e))
                LOGGER.error('Failed to sync endpoint {}, moving on!'
                             .format(stream_obj.TABLE))

        self.save_state(self.state)


@singer.utils.handle_top_exception(LOGGER)
def main():
    args = singer.utils.parse_args(required_config_keys=[
        'client_id',
        'client_secret',
        'refresh_token',
        'api_url',
        'start_date'
    ])

    client = RingCentralClient(args.config, args.config_path)

    runner = RingCentralRunner(args, client)

    if args.discover:
        runner.do_discover()
    elif args.catalog:
        runner.do_sync()


if __name__ == '__main__':
    main()
