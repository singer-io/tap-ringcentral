import requests
import base64
import backoff
import time
import json
import singer
import singer.metrics

from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta


LOGGER = singer.get_logger()  # noqa


class APIException(Exception):
    pass


class AuthFailedException(APIException):
    """Raised when authentication fails irrecoverably"""
    pass


class RingCentralClient:

    MAX_TRIES = 7

    def __init__(self, config, config_path):
        self.config = config
        self.config_path = config_path
        self.base_url = self.config.get('api_url')

        self.refresh_token = self.config.get('refresh_token')
        self.access_token = self.config.get('access_token')
    
        self.ensure_authorization()

    def write_config(self, data):
        self.config.update(data)
        with open(self.config_path, "w") as tap_config:
            json.dump(self.config, tap_config, indent=2)

    def is_refresh_token_expired(self):
        expires_at = self.config.get('refresh_token_expires_at')
        if not expires_at:
            return True
        return datetime.now() >= datetime.fromisoformat(expires_at)

    def is_access_token_expired(self):
        expires_at = self.config.get('access_token_expires_at')
        if not expires_at:
            return True
        return datetime.now() >= datetime.fromisoformat(expires_at)

    def ensure_authorization(self):
        if self.is_refresh_token_expired():
            LOGGER.error(
                "Authentication failed: your refresh token has expired and must be rotated. "
                "Please re-authenticate to obtain a new refresh token."
            )
            raise AuthFailedException("Refresh token expired - auth failed")

        if self.is_access_token_expired():
            self.get_authorization()

    def get_authorization(self):
        client_id = self.config.get('client_id')
        client_secret = self.config.get('client_secret')
        auth = HTTPBasicAuth(client_id, client_secret)

        payload = {
            'refresh_token': self.config.get('refresh_token'),
            'grant_type': 'refresh_token'
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.request(
            'POST',
            '{}/restapi/oauth/token'.format(self.base_url),
            auth=auth,
            headers=headers,
            data=payload)

        response.raise_for_status()
        data = response.json()

        now = datetime.now()
        access_token_expires_at = (now + timedelta(seconds=data['expires_in'])).isoformat()
        refresh_token_expires_at = (now + timedelta(seconds=data['refresh_token_expires_in'])).isoformat()

        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']

        self.write_config({
            'access_token': data['access_token'],
            'expires_in': data['expires_in'],
            'access_token_expires_at': access_token_expires_at,
            'refresh_token': data['refresh_token'],
            'refresh_token_expires_in': data['refresh_token_expires_in'],
            'refresh_token_expires_at': refresh_token_expires_at
        })

    @backoff.on_exception(backoff.expo,
                          APIException,
                          max_tries=MAX_TRIES)
    def make_request(self, url, method, params=None, body=None):
        LOGGER.info("Making {} request to {} ({})".format(method, url, params))

        response = requests.request(
            method,
            url,
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(self.access_token),
                'User-Agent': self.config.get('user_agent', 'tap-ringcentral')
            },
            params=params,
            json=body)

        LOGGER.info("Got status code {}".format(response.status_code))


        if response.status_code == 429:
            timeout = response.headers['Retry-After']
            LOGGER.info("Rate limit status code received, waiting {} seconds".format(timeout))
            time.sleep(int(timeout))
            raise APIException("Rate limit exceeded")

        elif response.status_code in [401, 403]:
            # Unauthorized - has the token expired?
            self.refresh_token, self.access_token = self.get_authorization()
            raise APIException("Token expired - refetching")

        elif response.status_code != 200:
            raise APIException(response.text)

        return response.json()
