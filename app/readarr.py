from __future__ import annotations

import httpx

from .config import ReadarrTargetSettings


class ReadarrClient:
    def __init__(self, target: ReadarrTargetSettings):
        self.target = target

    async def request_book(self, title: str, author: str, goodreads_id: str | None = None) -> str:
        timeout = httpx.Timeout(20.0, connect=5.0, read=20.0, write=20.0, pool=5.0)
        headers = {'X-Api-Key': self.target.api_key}
        async with httpx.AsyncClient(timeout=timeout) as client:
            author_resource = await self._lookup_or_create_author(client, headers, author)
            book_resource = await self._lookup_book(client, headers, title)
            monitored_book = self._normalize_book(book_resource, author_resource, goodreads_id)
            add_response = await client.post(f'{self.target.base_url}/api/v1/book', headers=headers, json=monitored_book)

        if add_response.status_code >= 400:
            raise ValueError(f'Readarr book add failed: {self._format_error(add_response)}')

        return 'Requested successfully'

    async def search_existing(self, client: httpx.AsyncClient, headers: dict[str, str], author_id: int, book_id: int) -> None:
        await client.post(f'{self.target.base_url}/api/v1/command', headers=headers, json={
            'name': 'SearchSingleBook',
            'sourceTitle': None,
            'bookIds': [book_id],
            'authorIds': [author_id],
        })

    async def _lookup_or_create_author(self, client: httpx.AsyncClient, headers: dict[str, str], author_name: str) -> dict:
        lookup = await client.get(f'{self.target.base_url}/api/v1/author/lookup', headers=headers, params={'term': author_name})
        if lookup.status_code >= 400:
            raise ValueError(f'Readarr author lookup failed: {self._format_error(lookup)}')
        authors = lookup.json()
        if not authors:
            raise ValueError(f'No Readarr author found for {author_name}')
        candidate = authors[0]
        existing = await self._get_author_by_id(client, headers, candidate.get('id'))
        if existing is not None:
            return existing
        created = await self._create_author(client, headers, candidate, author_name)
        return created

    async def _get_author_by_id(self, client: httpx.AsyncClient, headers: dict[str, str], author_id: int | None) -> dict | None:
        if author_id is None:
            return None
        response = await client.get(f'{self.target.base_url}/api/v1/author/{author_id}', headers=headers)
        if response.status_code == 200:
            return response.json()
        return None

    async def _create_author(self, client: httpx.AsyncClient, headers: dict[str, str], lookup_author: dict, author_name: str) -> dict:
        root_folder = await self._first_root_folder(client, headers)
        quality_profile = await self._first_quality_profile(client, headers)
        metadata_profile = await self._first_metadata_profile(client, headers)
        if not root_folder or not quality_profile or not metadata_profile:
            raise ValueError('Readarr author add failed: missing root folder or profile configuration')

        payload = {
            'authorName': lookup_author.get('authorName') or lookup_author.get('name') or author_name,
            'foreignAuthorId': lookup_author.get('foreignAuthorId'),
            'monitored': True,
            'monitorNewItems': 'all',
            'qualityProfileId': quality_profile,
            'metadataProfileId': metadata_profile,
            'rootFolderPath': root_folder,
            'path': f"{root_folder.rstrip('/')}/{self._sanitize(author_name)}",
            'addOptions': {
                'monitor': 'all',
                'searchForMissingBooks': True,
                'booksToMonitor': [],
            },
        }
        response = await client.post(f'{self.target.base_url}/api/v1/author', headers=headers, json=payload)
        if response.status_code >= 400:
            raise ValueError(f'Readarr author add failed: {self._format_error(response)}')
        return response.json()

    async def _lookup_book(self, client: httpx.AsyncClient, headers: dict[str, str], title: str) -> dict:
        lookup = await client.get(f'{self.target.base_url}/api/v1/book/lookup', headers=headers, params={'term': title})
        if lookup.status_code >= 400:
            raise ValueError(f'Readarr book lookup failed: {self._format_error(lookup)}')
        books = lookup.json()
        if not books:
            raise ValueError(f'No Readarr book found for {title}')
        return books[0]

    async def _first_root_folder(self, client: httpx.AsyncClient, headers: dict[str, str]) -> str | None:
        response = await client.get(f'{self.target.base_url}/api/v1/rootfolder', headers=headers)
        if response.status_code >= 400:
            return None
        folders = response.json()
        return folders[0].get('path') if folders else None

    async def _first_quality_profile(self, client: httpx.AsyncClient, headers: dict[str, str]) -> int | None:
        response = await client.get(f'{self.target.base_url}/api/v1/qualityprofile', headers=headers)
        if response.status_code >= 400:
            return None
        profiles = response.json()
        return profiles[0].get('id') if profiles else None

    async def _first_metadata_profile(self, client: httpx.AsyncClient, headers: dict[str, str]) -> int | None:
        response = await client.get(f'{self.target.base_url}/api/v1/metadataprofile', headers=headers)
        if response.status_code >= 400:
            return None
        profiles = response.json()
        return profiles[0].get('id') if profiles else None

    def _normalize_book(self, book: dict, author: dict, goodreads_id: str | None) -> dict:
        editions = book.get('editions') or []
        selected_edition = editions[0] if editions else None
        payload = {
            'title': book.get('title'),
            'author': author,
            'authorId': author.get('id'),
            'foreignBookId': goodreads_id or book.get('foreignBookId'),
            'foreignEditionId': book.get('foreignEditionId') or (selected_edition or {}).get('foreignEditionId'),
            'monitored': True,
            'anyEditionOk': False,
            'addOptions': {
                'addType': 'automatic',
                'searchForNewBook': True,
            },
            'editions': [self._normalize_edition(book, selected_edition)] if selected_edition or book else [],
        }
        return {k: v for k, v in payload.items() if v is not None}

    def _normalize_edition(self, book: dict, edition: dict | None) -> dict:
        if edition is None:
            return {
                'title': book.get('title'),
                'foreignEditionId': book.get('foreignEditionId') or book.get('foreignBookId') or str(book.get('id') or ''),
                'isEbook': False,
                'monitored': True,
                'manualAdd': True,
                'pageCount': book.get('pageCount', 0),
                'overview': book.get('overview'),
                'images': book.get('images') or [],
                'links': book.get('links') or [],
                'ratings': book.get('ratings') or {'votes': 0, 'value': 0},
            }
        return {
            'id': edition.get('id'),
            'foreignEditionId': edition.get('foreignEditionId'),
            'title': edition.get('title') or book.get('title'),
            'language': edition.get('language'),
            'overview': edition.get('overview') or book.get('overview'),
            'format': edition.get('format'),
            'isEbook': edition.get('isEbook', False),
            'disambiguation': edition.get('disambiguation'),
            'publisher': edition.get('publisher'),
            'pageCount': edition.get('pageCount', 0),
            'releaseDate': edition.get('releaseDate'),
            'images': edition.get('images') or book.get('images') or [],
            'links': edition.get('links') or book.get('links') or [],
            'ratings': edition.get('ratings') or book.get('ratings') or {'votes': 0, 'value': 0},
            'monitored': True,
            'manualAdd': True,
        }

    def _sanitize(self, value: str) -> str:
        out = []
        for ch in value:
            out.append(ch if ch.isalnum() or ch in {' ', '-', '_', '.', '(', ')'} else '_')
        return ''.join(out).strip().replace('  ', ' ')

    def _format_error(self, response: httpx.Response) -> str:
        return response.text.strip() or response.reason_phrase
