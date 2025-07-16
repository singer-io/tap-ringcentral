import inspect
import math
import os
import pytz
import singer
import singer.utils
import singer.metrics
import time

from datetime import timedelta, datetime

import tap_ringcentral.cache
from tap_ringcentral.config import get_config_start_date
from tap_ringcentral.state import incorporate, save_state, \
    get_last_record_value_for_table

from singer import metadata as meta

LOGGER = singer.get_logger()


class BaseStream:
    KEY_PROPERTIES = ['id']
    TABLE = None
    REQUIRES = []

    def __init__(self, config, state, catalog, client):
        self.config = config
        self.state = state
        self.catalog = catalog
        self.client = client
        self.substreams = []

    def get_class_path(self):
        return os.path.dirname(inspect.getfile(self.__class__))

    def load_schema_by_name(self, name):
        return singer.utils.load_json(
            os.path.normpath(
                os.path.join(
                    self.get_class_path(),
                    '../schemas/{}.json'.format(name))))

    def get_schema(self):
        return self.load_schema_by_name(self.TABLE)

    def get_params(self, page=1):
        return {
            "page": page,
            "per_page": 1000
        }

    def get_body(self):
        return {}

    def get_url(self, path):
        return '{}{}'.format(BASE_URL, path)

    def get_stream_data(self, result, contact_id):
        xf = []
        for record in result['records']:
            record_xf = self.transform_record(record)
            record_xf['_contact_id'] = contact_id
            xf.append(record_xf)
        return xf

    def transform_record(self, record):
        with singer.Transformer() as tx:
            metadata = {}

            if self.catalog.metadata is not None:
                metadata = singer.metadata.to_map(self.catalog.metadata)

            return tx.transform(
                record,
                self.catalog.schema.to_dict(),
                metadata)

    def write_schema(self):
        singer.write_schema(
            self.catalog.stream,
            self.catalog.schema.to_dict(),
            key_properties=self.catalog.key_properties)

    def sync(self):
        LOGGER.info('Syncing stream {} with {}'
                    .format(self.catalog.tap_stream_id,
                            self.__class__.__name__))

        self.write_schema()

        return self.sync_data()

    def sync_data(self):
        table = self.TABLE
        page = 1

        LOGGER.info('Syncing data for entity {} (page={})'.format(table, page))

        url = "{}{}".format(self.client.base_url, self.api_path)

        while True:
            params = self.get_params(page=page)
            body = self.get_body()

            result = self.client.make_request(
                url, self.API_METHOD, params=params, body=body)

            data = self.get_stream_data(result)

            with singer.metrics.record_counter(endpoint=table) as counter:
                for obj in data:
                    singer.write_records(
                        table,
                        [obj])

                    counter.increment()

            paging = result['paging']
            if page >= paging['totalPages']:
                break
            page += 1

        return self.state

class ContactBaseStream(BaseStream):
    KEY_PROPERTIES = ['id']

    def sync_data(self):
        table = self.TABLE
        LOGGER.info('Syncing data for entity {}'.format(table))

        date = get_last_record_value_for_table(self.state, table)

        if date is None:
            date = get_config_start_date(self.config)

        interval = timedelta(days=7)

        while date < datetime.now(pytz.utc):
            self.sync_data_for_period(date, interval)

            date = date + interval
            save_state(self.state)

    def sync_data_for_period(self, date, interval):
        for extension in tap_ringcentral.cache.contacts:
            extensionId = extension['id']
            self.sync_data_for_extension(date, interval, extensionId)

        self.state = incorporate(self.state, self.TABLE, 'last_record', date.isoformat())
        return self.state

    def get_params(self, date_from, date_to, page, per_page):
        return {
            "page": page,
            "perPage": per_page,
            "dateFrom": date_from,
            "dateTo": date_to,
            "showDeleted": True,
        }

    def get_stream_data(self, result, contact_id):
        xf = []
        for record in result['records']:
            record_xf = self.transform_record(record)
            record_xf['_contact_id'] = contact_id
            xf.append(record_xf)
        return xf

    def sync_data_for_extension(self, date, interval, extensionId):
        table = self.TABLE

        page = 1
        per_page = 100

        date_from = date.isoformat()
        date_to = (date + interval).isoformat()

        while True:
            LOGGER.info('Syncing {} for contact={} from {} to {}, page={}'.format(
                table,
                extensionId,
                date_from,
                date_to,
                page
            ))

            params = self.get_params(date_from, date_to, page, per_page)
            body = self.get_body()

            url = "{}{}".format(
                self.client.base_url,
                self.api_path.format(extensionId=extensionId)
            )

            # The API rate limits us pretty aggressively
            time.sleep(5)

            result = self.client.make_request(
                url, self.API_METHOD, params=params, body=body)

            data = self.get_stream_data(result, extensionId)

            with singer.metrics.record_counter(endpoint=table) as counter:
                singer.write_records(table, data)
                counter.increment(len(data))

            if len(data) < per_page:
                break

            page += 1
