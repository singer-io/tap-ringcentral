import json as json_mod
import unittest
from unittest.mock import patch, MagicMock
import requests
from tap_ringcentral.client import RingCentralClient, APIException, AuthFailedException


class MockResponse:
    """Mock response object class."""
    def __init__(self, status_code, json, raise_error, headers=None, text=None):
        self.status_code = status_code
        self.raise_error = raise_error
        self.text = json_mod.dumps(json) if text is None else text
        self.headers = headers or {}
        self._json = json

    def raise_for_status(self):
        if not self.raise_error:
            return self.status_code
        raise requests.HTTPError("Sample message")

    def json(self):
        """Response JSON method."""
        return self._json


def get_response(status_code, json=None, headers=None, raise_error=False, text=None):
    """Returns required mock response."""
    return MockResponse(status_code, json if json is not None else {}, raise_error, headers, text)


class TestGetAuthorization(unittest.TestCase):
    """
    Unit tests for the `get_authorization` method of the RingCentralClient class.

    This test class verifies that:
      - A successful token refresh returns the new refresh and access tokens.
      - An expired or invalid refresh token raises AuthFailedException.
      - The config file is updated with the new refresh token on success.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        self.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        self.config_path = "test_config.json"

    @patch("builtins.open", new_callable=MagicMock)
    @patch("json.dump")
    @patch("requests.request")
    def test_successful_authorization(self, mock_request, mock_json_dump, mock_open):
        """
        Test that `get_authorization` returns the new refresh and access tokens
        when the API responds successfully.
        """
        mock_request.return_value = get_response(
            200,
            json={"refresh_token": "new_refresh_token", "access_token": "new_access_token"},
        )

        client = RingCentralClient(self.config, self.config_path)
        self.assertEqual(client.refresh_token, "new_refresh_token")
        self.assertEqual(client.access_token, "new_access_token")

    @patch("requests.request")
    def test_expired_refresh_token_raises_auth_failed(self, mock_request):
        """
        Test that `get_authorization` raises AuthFailedException when the API
        returns a 400 error with 'invalid_grant' in the response text.
        """
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant", "error_description": "Token is expired"}'
        mock_request.return_value = mock_response

        with self.assertRaises(AuthFailedException) as context:
            RingCentralClient(self.config, self.config_path)
        self.assertIn("Refresh token expired or invalid", str(context.exception))

    @patch("requests.request")
    def test_server_error_raises_http_error(self, mock_request):
        """
        Test that `get_authorization` raises an HTTPError when the API returns
        a non-400 error status code.
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_request.return_value = mock_response

        with self.assertRaises(requests.HTTPError):
            RingCentralClient(self.config, self.config_path)

    @patch("builtins.open", new_callable=MagicMock)
    @patch("json.dump")
    @patch("requests.request")
    def test_config_updated_on_success(self, mock_request, mock_json_dump, mock_open):
        """
        Test that `get_authorization` writes the new refresh token to the config file.
        """
        mock_request.return_value = get_response(
            200,
            json={"refresh_token": "new_refresh_token", "access_token": "new_access_token"},
        )

        client = RingCentralClient(self.config, self.config_path)
        # Verify config was updated
        self.assertEqual(client.config["refresh_token"], "new_refresh_token")
        mock_open.assert_called_once_with(self.config_path, "w")


@patch("builtins.open", new_callable=MagicMock)
@patch("json.dump")
@patch("requests.request")
class TestMakeRequest(unittest.TestCase):
    """
    Unit tests for verifying the behavior of the RingCentralClient class's HTTP request handling.

    This test class specifically focuses on testing the `make_request` method of the RingCentralClient class,
    ensuring that:

    - HTTP requests are made with the expected headers, parameters, and authorization.
    - The client handles successful responses correctly.
    - Rate limiting (429) triggers a retry via APIException.
    - Unauthorized (401/403) triggers token refresh via APIException.
    - Other error status codes raise APIException.

    External calls (such as token refresh or network requests) are mocked to isolate test behavior
    and avoid making real API calls.
    """

    def setUp(self):
        """Set up common test configuration before each test case runs."""
        self.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
            "user_agent": "tap-ringcentral",
        }
        self.config_path = "test_config.json"
        self.url = "https://platform.ringcentral.com/restapi/v1.0/test"
        self.method = "GET"
        self.auth_response = get_response(
            200,
            json={"refresh_token": "new_refresh_token", "access_token": "test_access_token"},
        )

    def _create_client(self, mock_request):
        """Helper to create a client with mocked authorization.
        After creation, the mock's call list is reset so API call assertions are clean."""
        mock_request.return_value = self.auth_response
        client = RingCentralClient(self.config.copy(), self.config_path)
        mock_request.reset_mock()
        return client

    def test_successful_request(self, mock_request, mock_json_dump, mock_open):
        """Test case for a successful API request."""
        client = self._create_client(mock_request)
        mock_request.return_value = get_response(200, json={"records": []})

        result = client.make_request(self.url, self.method, params={"page": 1})
        self.assertEqual(result, {"records": []})
        mock_request.assert_called_once()

    def test_request_headers(self, mock_request, mock_json_dump, mock_open):
        """Test that requests are made with the correct authorization headers."""
        client = self._create_client(mock_request)
        mock_request.return_value = get_response(200, json={"records": []})

        client.make_request(self.url, self.method)

        call_args = mock_request.call_args
        # requests.request is called positionally: request(method, url, headers=..., ...)
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer test_access_token")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["User-Agent"], "tap-ringcentral")

    @patch("tap_ringcentral.client.time.sleep")
    def test_rate_limit_error(self, mock_sleep, mock_request, mock_json_dump, mock_open):
        """Test case for 429 Rate Limit error triggers APIException for retry."""
        client = self._create_client(mock_request)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        mock_response.text = "Rate limit exceeded"
        mock_request.return_value = mock_response

        with self.assertRaises(APIException) as context:
            client.make_request(self.url, self.method)
        self.assertIn("Rate limit exceeded", str(context.exception))

    def test_unauthorized_error_triggers_token_refresh(self, mock_request, mock_json_dump, mock_open):
        """Test case for 401 Unauthorized error triggers token refresh and successful retry."""
        client = self._create_client(mock_request)

        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.text = "Unauthorized"

        mock_request.side_effect = [
            mock_response_401,  # make_request API call returns 401
            self.auth_response,  # get_authorization refresh call
            get_response(200, json={"records": ["retried"]}),  # retry succeeds after token refresh
        ]

        result = client.make_request(self.url, self.method)
        self.assertEqual(result, {"records": ["retried"]})
        # Verify request was called 3 times (initial API + auth refresh + retry)
        self.assertEqual(mock_request.call_count, 3)

    def test_forbidden_error_triggers_token_refresh(self, mock_request, mock_json_dump, mock_open):
        """Test case for 403 Forbidden error triggers token refresh and successful retry."""
        client = self._create_client(mock_request)

        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403
        mock_response_403.text = "Forbidden"

        mock_request.side_effect = [
            mock_response_403,  # make_request API call returns 403
            self.auth_response,  # get_authorization refresh call
            get_response(200, json={"records": ["retried"]}),  # retry succeeds after token refresh
        ]

        result = client.make_request(self.url, self.method)
        self.assertEqual(result, {"records": ["retried"]})
        # Verify request was called 3 times (initial API + auth refresh + retry)
        self.assertEqual(mock_request.call_count, 3)

    def test_other_error_status_raises_api_exception(self, mock_request, mock_json_dump, mock_open):
        """Test case for non-200/429/401/403 error status raises APIException."""
        client = self._create_client(mock_request)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        with self.assertRaises(APIException) as context:
            client.make_request(self.url, self.method)
        self.assertIn("Internal Server Error", str(context.exception))


class TestWriteConfig(unittest.TestCase):
    """
    Unit tests for the `write_config` method of the RingCentralClient class.
    """

    @patch("builtins.open", new_callable=MagicMock)
    @patch("json.dump")
    @patch("requests.request")
    def test_write_config_updates_config(self, mock_request, mock_json_dump, mock_open):
        """Test that write_config updates the in-memory config and writes to file."""
        mock_request.return_value = get_response(
            200,
            json={"refresh_token": "new_token", "access_token": "new_access"},
        )
        config = {
            "client_id": "test_id",
            "client_secret": "test_secret",
            "refresh_token": "old_token",
            "api_url": "https://platform.ringcentral.com",
            "start_date": "2025-01-01T00:00:00Z",
        }
        client = RingCentralClient(config, "test_config.json")
        client.write_config({"refresh_token": "updated_token"})

        self.assertEqual(client.config["refresh_token"], "updated_token")


if __name__ == "__main__":
    unittest.main()
