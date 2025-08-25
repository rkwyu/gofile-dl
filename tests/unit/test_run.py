import logging
import unittest
from unittest.mock import patch, MagicMock
import run


class TestRun(unittest.TestCase):
    
    def setUp(self):
        self.gofile = run.GoFile()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    @patch("requests.post")
    def test_update_token(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "id": "f87df49a-b388-4ae5-bced-569cacd1a11c",
                "rootFolder": "d7a8630b-6baa-47fb-a0bf-a8e011d67b13",
                "tier": "guest",
                "token": "iRnBCMHkrRg7gvDESTAXql2Fky0CEWeB",
            },
        }
        mock_post.return_value = mock_response
        self.gofile.update_token()
        self.assertEqual(self.gofile.token, "iRnBCMHkrRg7gvDESTAXql2Fky0CEWeB")

    @patch("requests.get")
    def test_update_wt(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
            ...
            appdata.servers.timestamp = null;
            appdata.wt = "4fd6sg89d7s6"
            appdata.apiServer = "api"
            ...
        """
        mock_get.return_value = mock_response
        self.gofile.update_wt()
        self.assertEqual(self.gofile.wt, "4fd6sg89d7s6")

    @patch.object(run.GoFile, "update_token")
    @patch.object(run.GoFile, "update_wt")
    @patch.object(run.GoFile, "download")
    @patch("requests.get")
    def test_execute(self, mock_get, mock_download, mock_update_wt, mock_update_token):
        mock_update_token.return_value = None
        mock_update_wt.return_value = None
        mock_download.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "type": "folder",
                "name": "kaori_xoxo",
                "children": {
                    "29754b9e-7e71-4074-809f-06b241b17428": {
                        "type": "file",
                        "name": "name",
                        "link": "https://store8.gofile.io/download/web/29754b9e-7e71-4074-809f-06b241b17428/.mp4",
                    }
                },
            },
        }
        mock_get.return_value = mock_response
        self.gofile.execute(dir="./output", url="https://gofile.io/d/xyz")
        mock_update_token.assert_called_once()
        mock_update_wt.assert_called_once()
        mock_download.assert_called_once()


if __name__ == "__main__":
    unittest.main()
