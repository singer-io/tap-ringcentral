import inspect
import math
import os
import re
import pytz
import singer
import singer.utils
import singer.metrics
import time
from typing import ClassVar, Optional

from datetime import timedelta, datetime
from dateutil.parser import parse

import tap_ringcentral.cache
from tap_ringcentral.config import get_config_start_date
from tap_ringcentral.client import RingCentralForbiddenError
from tap_ringcentral.state import migrate_bookmark_format
from singer import metadata as meta
from singer import get_bookmark, write_bookmark

LOGGER = singer.get_logger()


class BaseStream:
    KEY_PROPERTIES = ['id']
    TABLE: Optional[str] = None
    REQUIRES: ClassVar[list] = []
    parent: Optional[str] = None
    REPLICATION_METHOD: ClassVar[Optional[str]] = None
    REPLICATION_KEYS: ClassVar[list] = []
    # Subclasses should override these attributes
    api_path: str
    API_METHOD: ClassVar[str]

    def __init__(self, config=None, state=None, catalog=None, client=None):
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
        return '{}{}'.format(self.client.base_url, path)

    def check_access(self) -> bool:
        """
        Verify that the API credentials have read access to this stream.
        Returns True if accessible, False if a 403 Forbidden error is raised.
        Child streams (where parent is set) always return True; their
        removal from the catalog is handled by _prune_inaccessible_children.
        """
        if self.parent:
            return True

        url_template = "{}{}".format(self.client.base_url, self.api_path)
        # Replace any {placeholder} (e.g. {extensionId}) with '~' for the probe
        url = re.sub(r'\{[^}]+\}', '~', url_template)

        params = self.params if hasattr(self, 'params') else {"page": 1, "perPage": 1}

        try:
            self.client.make_request(url, self.API_METHOD, params=params)
            return True
        except RingCentralForbiddenError as exc:
            LOGGER.warning(
                "Unauthorized Stream: %s, excluding from catalog. HTTP-Error-Message: '%s'",
                self.__class__.__name__,
                str(exc)
            )
            return False

    def get_stream_data(self, result, contact_id=None):
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

        replication_key = self.REPLICATION_KEYS[0] if self.REPLICATION_KEYS else 'processedUntil'
        # Migrate state written by older versions of the tap before reading
        self.state = migrate_bookmark_format(self.state, table, replication_key)

        bookmark_str = get_bookmark(
            self.state,
            table,
            key=replication_key,
            default=get_config_start_date(self.config)
        )

        # Parse bookmark to datetime
        date = parse(bookmark_str) if isinstance(bookmark_str, str) else bookmark_str

        interval = timedelta(days=7)

        while date < datetime.now(pytz.utc):
            self.sync_data_for_period(date, interval)

            date = date + interval

    def sync_data_for_period(self, date, interval):
        records_synced = 0
        replication_key = self.REPLICATION_KEYS[0] if self.REPLICATION_KEYS else 'processedUntil'

        for extension in tap_ringcentral.cache.contacts:
            extensionId = extension['id']
            extension_records = self.sync_data_for_extension(date, interval, extensionId)
            records_synced += extension_records

        # Only advance bookmark if records were actually synced
        if records_synced > 0:
            self.state = write_bookmark(
                self.state,
                self.TABLE,
                replication_key,
                date.isoformat()
            )
            LOGGER.info(
                'Synced %d records for %s. Bookmark advanced to %s',
                records_synced, self.TABLE, date.isoformat()
            )
        else:
            LOGGER.warning(
                'No records synced for %s in period ending %s. Bookmark not advanced.',
                self.TABLE, date.isoformat()
            )

        return self.state

    def get_params(self, date_from, date_to, page, per_page):
        return {
            "page": page,
            "perPage": per_page,
            "dateFrom": date_from,
            "dateTo": date_to,
            "showDeleted": True,
        }

    def get_stream_data(self, result, contact_id=None):
        xf = []
        for record in result['records']:
            record_xf = self.transform_record(record)
            record_xf['_contact_id'] = contact_id
            xf.append(record_xf)
        return xf

    def sync_data_for_extension(self, date, interval, extensionId):
        table = self.TABLE
        total_records = 0

        try:
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
                    total_records += len(data)

                if len(data) < per_page:
                    break

                page += 1
        except RingCentralForbiddenError as e:
            LOGGER.warning(
                "Permission denied for stream '%s' on extension '%s': %s. Skipping this extension.",
                table,
                extensionId,
                str(e)
            )

        return total_records
