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

            payload = {
                'title': title,
                'author': author_resource,
                'monitored': True,
                'searchForNewBook': True,
                'addOptions': {
                    'searchForBook': True,
                },
            }
            if goodreads_id:
                payload['foreignBookId'] = goodreads_id

            response = await client.post(f'{self.target.base_url}/api/v1/book', headers=headers, json=payload)

        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise ValueError(f'Readarr rejected request: {detail}')

        return 'Requested successfully'
