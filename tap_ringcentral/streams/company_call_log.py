from tap_ringcentral.streams.base import ContactBaseStream

import singer
import json
from singer import write_bookmark

LOGGER = singer.get_logger()  # noqa


class CompanyCallLogStream(ContactBaseStream):
    NAME = 'CompanyCallLogStream'
    KEY_PROPERTIES = ['id']
    REPLICATION_METHOD = 'INCREMENTAL'
    REPLICATION_KEYS = ['processedUntil']
    REQUIRES = []
    API_METHOD = 'GET'
    TABLE = 'company_call_log'

    @property
    def api_path(self):
        return '/restapi/v1.0/account/~/call-log'

    def sync_data_for_period(self, date, interval):
        records_synced = self.sync_data_for_extension(date, interval, None)

        # Only advance bookmark if records were actually synced
        if records_synced > 0:
            self.state = write_bookmark(
                self.state,
                self.TABLE,
                self.REPLICATION_KEYS[0] if self.REPLICATION_KEYS else 'processedUntil',
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
