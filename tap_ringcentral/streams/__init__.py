
from tap_ringcentral.streams.contacts import ContactsStream
from tap_ringcentral.streams.call_log import CallLogStream
from tap_ringcentral.streams.company_call_log import CompanyCallLogStream
from tap_ringcentral.streams.messages import MessageStream


AVAILABLE_STREAMS = {
    "contacts": ContactsStream,
    "call_log": CallLogStream,
    "company_call_log": CompanyCallLogStream,
    "messages": MessageStream,
}


__all__ = [s.NAME for s in AVAILABLE_STREAMS.values()]
