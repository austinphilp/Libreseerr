import logging

import requests

logger = logging.getLogger(__name__)


class AudiobookshelfClient:
    """Read-only client for checking library contents on an Audiobookshelf instance."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_token}"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def test_connection(self) -> dict:
        """Test connection by calling the authorize endpoint."""
        resp = self.session.get(self._url("/api/authorize"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_downloaded_titles(self) -> set:
        """Return a set of lowercase book titles across all book libraries."""
        resp = self.session.get(self._url("/api/libraries"), timeout=15)
        resp.raise_for_status()
        libraries = resp.json().get("libraries", [])

        titles = set()
        for lib in libraries:
            if lib.get("mediaType") != "book":
                continue
            lib_id = lib.get("id")
            if not lib_id:
                continue
            try:
                items_resp = self.session.get(
                    self._url(f"/api/libraries/{lib_id}/items"),
                    params={"limit": 0},
                    timeout=60,
                )
                items_resp.raise_for_status()
                for item in items_resp.json().get("results", []):
                    title = (
                        item.get("media", {})
                        .get("metadata", {})
                        .get("title", "")
                    )
                    if title:
                        titles.add(title.lower())
            except Exception as e:
                logger.warning(
                    "Failed to fetch items for library %s: %s", lib_id, e
                )
        return titles
