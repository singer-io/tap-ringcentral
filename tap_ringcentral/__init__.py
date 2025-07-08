#!/usr/bin/env python3

import singer
import sys

import argparse
import json

from tap_ringcentral.discover import discover

from tap_ringcentral.client import RingCentralClient
from tap_ringcentral.streams import STREAMS
from tap_ringcentral.streams.base import is_stream_selected

LOGGER = singer.get_logger()  # noqa


class RingCentralRunner:
    def __init__(self, args, client):
        self.config = args.config
        self.state = args.state
        self.catalog = args.catalog
        self.client = client
        self.available_streams = STREAMS.values()

    def save_state(self, state):
        if not state:
            return
        LOGGER.info('Updating state.')
        singer.write_state(state)

    def do_discover(self):
        LOGGER.info("Starting discovery")
        catalog = discover()
        json.dump(catalog.to_dict(), sys.stdout, indent=2)
        LOGGER.info("Finished discover")

    def get_streams_to_replicate(self):
        streams = []

        if not self.catalog:
            return streams

        for stream_catalog in self.catalog.streams:
            if not is_stream_selected(stream_catalog):
                LOGGER.info("'{}' is not marked selected, skipping."
                            .format(stream_catalog.stream))
                continue

            for available_stream in self.available_streams:
                if available_stream.matches_catalog(stream_catalog):
                    if not available_stream.requirements_met(self.catalog):
                        raise RuntimeError(
                            "{} requires that the following are "
                            "selected: {}".format(
                                stream_catalog.stream,
                                ",".join(available_stream.REQUIRES),
                            )
                        )
                    to_add = available_stream(
                        self.config, self.state, stream_catalog, self.client
                    )
                    streams.append(to_add)

        return streams

    # Sync the streams in the order specified in the
    # streams/__init__.py list of AVAILABLE_STREAMS
    def do_sync(self):
        LOGGER.info("Starting sync.")

        streams = self.get_streams_to_replicate()
        stream_map = {s.NAME: s for s in streams}

        for available_stream in STREAMS.values():
            if available_stream.NAME not in stream_map:
                continue

            stream = stream_map[available_stream.NAME]
            try:
                stream.state = self.state
                stream.sync()
                self.state = stream.state
            except OSError as e:
                LOGGER.error(str(e))
                exit(e.errno)

            except Exception as e:
                LOGGER.error(str(e))
                LOGGER.error('Failed to sync endpoint {}, moving on!'
                             .format(stream.TABLE))
                raise e

        self.save_state(self.state)


@singer.utils.handle_top_exception(LOGGER)
def main():
    args = singer.utils.parse_args(required_config_keys=[
        'client_id',
        'client_secret',
        'username',
        'password',
        'api_url',
        'start_date'
    ])

    client = RingCentralClient(args.config)

    runner = RingCentralRunner(args, client)

    if args.discover:
        runner.do_discover()
    else:
        runner.do_sync()


if __name__ == '__main__':
    main()
