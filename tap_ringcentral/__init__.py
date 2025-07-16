#!/usr/bin/env python3

import singer
import sys

import argparse
import json

from tap_ringcentral.discover import discover

from tap_ringcentral.client import RingCentralClient
from tap_ringcentral.streams import AVAILABLE_STREAMS

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
        catalog = discover()
        json.dump(catalog.to_dict(), sys.stdout, indent=2)
        LOGGER.info("Finished discover")


    # Sync the streams in the order specified in the
    # streams/__init__.py list of AVAILABLE_STREAMS
    def do_sync(self):
        LOGGER.info("Starting sync.")

        for stream_to_sync in self.catalog.get_selected_streams(self.state):
            stream_obj = self.available_streams[stream_to_sync.stream](
                        self.config, self.state, stream_to_sync, self.client
                    )
            try:
                stream_obj.state = self.state
                stream_obj.sync()
                self.state = stream_obj.state
            except Exception as e:
                LOGGER.error(str(e))
                LOGGER.error('Failed to sync endpoint {}, moving on!'
                             .format(stream_obj.TABLE))
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
    elif args.catalog:
        runner.do_sync()


if __name__ == '__main__':
    main()
