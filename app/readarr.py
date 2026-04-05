from __future__ import annotations

import httpx

from .config import ReadarrTargetSettings


class ReadarrClient:
    def __init__(self, target: ReadarrTargetSettings):
        self.target = target

    async def request_book(self, title: str, author: str, goodreads_id: str | None = None) -> str:
        search_payload = {
            'term': title,
            'type': 'search',
        }
        add_payload = {
            'monitored': True,
            'searchForNewBook': True,
            'addOptions': {
                'searchForBook': True,
            },
            'title': title,
            'author': author,
        }
        if goodreads_id:
            add_payload['foreignBookId'] = goodreads_id

        headers = {'X-Api-Key': self.target.api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_response = await client.get(f'{self.target.base_url}/api/v1/search', headers=headers, params=search_payload)
            if search_response.status_code >= 400:
                raise ValueError(f'Readarr search failed: {search_response.text.strip() or search_response.reason_phrase}')

            response = await client.post(f'{self.target.base_url}/api/v1/book', headers=headers, json=add_payload)

        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise ValueError(f'Readarr rejected request: {detail}')

        return 'Requested successfully'
