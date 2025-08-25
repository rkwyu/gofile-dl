import logging
import unittest
import requests

GOFILE_API_URL = "https://api.gofile.io/servers"


class TestGofileAPI(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_gofile_servers(self):
        response = requests.get(GOFILE_API_URL)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("status", data)
        self.assertIn("data", data)
        self.assertIn("servers", data["data"])


if __name__ == "__main__":
    unittest.main()
