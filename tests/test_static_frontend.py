import unittest

from fastapi.testclient import TestClient

from api_app import app


class StaticFrontendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_root_serves_react_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<div id="root"></div>', response.text)

    def test_react_route_refresh_falls_back_to_index(self) -> None:
        response = self.client.get("/dashboard/demo-run")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root"></div>', response.text)

    def test_static_asset_is_served(self) -> None:
        index = self.client.get("/").text
        asset_path = index.split('src="/', 1)[1].split('"', 1)[0]

        response = self.client.get(f"/{asset_path}")

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
