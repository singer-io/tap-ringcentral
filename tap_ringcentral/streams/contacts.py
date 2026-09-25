from tap_ringcentral.streams.base import BaseStream
import tap_ringcentral.cache

import singer
import json

LOGGER = singer.get_logger()  # noqa


class ContactsStream(BaseStream):
    NAME = 'ContactsStream'
    KEY_PROPERTIES = ['id']
    REPLICATION_METHOD = 'FULL_TABLE'
    REPLICATION_KEYS = []
    API_METHOD = 'GET'
    TABLE = 'contacts'

    @property
    def api_path(self):
        return '/restapi/v1.0/account/~/directory/entries'

    def fill_cache(self):
        """Fetch extension IDs into cache without writing Singer records.

        Raises RingCentralForbiddenError if access is denied; the caller
        decides how to handle streams that depend on this cache.
        """
        page = 1
        url = "{}{}".format(self.client.base_url, self.api_path)
        while True:
            params = self.get_params(page=page)
            result = self.client.make_request(url, self.API_METHOD, params=params)
            tap_ringcentral.cache.contacts.extend(
                {'id': record['id']} for record in result['records']
            )
            paging = result['paging']
            if page >= paging['totalPages']:
                break
            page += 1

    def get_stream_data(self, result):
        contacts = [
            self.transform_record(record)
            for record in result['records']
        ]

        tap_ringcentral.cache.contacts.extend(contacts)
        return contacts
