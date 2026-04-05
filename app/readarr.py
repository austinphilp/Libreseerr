from __future__ import annotations

import httpx

from .config import ReadarrTargetSettings


class ReadarrClient:
    def __init__(self, target: ReadarrTargetSettings):
        self.target = target

    async def request_book(self, title: str, author: str, goodreads_id: str | None = None) -> str:
        headers = {'X-Api-Key': self.target.api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            author_search = await client.get(f'{self.target.base_url}/api/v1/author', headers=headers, params={'term': author})
            if author_search.status_code >= 400:
                raise ValueError(f'Readarr author search failed: {author_search.text.strip() or author_search.reason_phrase}')
            authors = author_search.json()
            if not authors:
                raise ValueError(f'No Readarr author found for {author}')
            author_resource = authors[0]

            book_search = await client.get(f'{self.target.base_url}/api/v1/search', headers=headers, params={'term': title})
            if book_search.status_code >= 400:
                raise ValueError(f'Readarr book search failed: {book_search.text.strip() or book_search.reason_phrase}')
            books = book_search.json()
            if not books:
                raise ValueError(f'No Readarr book found for {title}')

            selected = self._select_candidate(books, title)
            payload = {
                'title': selected.get('title', title),
                'author': author_resource,
                'foreignBookId': goodreads_id or selected.get('foreignBookId'),
                'edition': self._first_edition(selected),
                'monitored': True,
                'searchForNewBook': True,
                'addOptions': {
                    'searchForBook': True,
                },
            }

            if payload['edition'] is None:
                payload.pop('edition')

            response = await client.post(f'{self.target.base_url}/api/v1/book', headers=headers, json=payload)

        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise ValueError(f'Readarr rejected request: {detail}')

        return 'Requested successfully'

    def _select_candidate(self, books: list[dict], title: str) -> dict:
        normalized = title.casefold()
        for book in books:
            if book.get('title', '').casefold() == normalized:
                return book
        return books[0]

    def _first_edition(self, book: dict) -> dict | None:
        editions = book.get('editions') or []
        return editions[0] if editions else None
