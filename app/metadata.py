from __future__ import annotations

import httpx

GOOGLE_BOOKS_URL = 'https://www.googleapis.com/books/v1/volumes'
OPEN_LIBRARY_URL = 'https://openlibrary.org/search.json'


def _pick_isbn(identifiers: list[dict] | None) -> str | None:
    if not identifiers:
        return None
    for item in identifiers:
        if item.get('type') in {'ISBN_13', 'ISBN_10'} and item.get('identifier'):
            return item['identifier']
    return None


async def search_books(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(GOOGLE_BOOKS_URL, params={'q': query, 'maxResults': 20, 'printType': 'books'})
            if response.status_code == 429:
                raise httpx.HTTPStatusError('rate limited', request=response.request, response=response)
            response.raise_for_status()
            data = response.json()
            return _parse_google_books(data)
        except Exception:
            response = await client.get(OPEN_LIBRARY_URL, params={'q': query, 'limit': 20})
            response.raise_for_status()
            data = response.json()
            return _parse_open_library(data)


def _parse_google_books(data: dict) -> list[dict]:
    results = []
    for item in data.get('items', []):
        volume = item.get('volumeInfo', {})
        image_links = volume.get('imageLinks', {})
        results.append({
            'id': item.get('id'),
            'source': 'google',
            'title': volume.get('title', 'Unknown title'),
            'author': ', '.join(volume.get('authors', [])) if volume.get('authors') else 'Unknown author',
            'description': volume.get('description', 'No description available.'),
            'thumbnail': image_links.get('thumbnail') or image_links.get('smallThumbnail') or '',
            'isbn': _pick_isbn(volume.get('industryIdentifiers')),
        })
    return results


def _parse_open_library(data: dict) -> list[dict]:
    results = []
    for item in data.get('docs', []):
        cover = item.get('cover_i')
        isbn = item.get('isbn', [None])[0] if item.get('isbn') else None
        results.append({
            'id': item.get('key', '').removeprefix('/works/'),
            'source': 'openlibrary',
            'title': item.get('title', 'Unknown title'),
            'author': ', '.join(item.get('author_name', [])) if item.get('author_name') else 'Unknown author',
            'description': item.get('first_sentence', 'No description available.') if isinstance(item.get('first_sentence'), str) else 'No description available.',
            'thumbnail': f'https://covers.openlibrary.org/b/id/{cover}-L.jpg' if cover else '',
            'isbn': isbn,
        })
    return results


async def get_book(book_id: str, source: str = 'google') -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        if source == 'openlibrary':
            response = await client.get(f'https://openlibrary.org/works/{book_id}.json')
            if response.status_code == 404:
                return None
            response.raise_for_status()
            item = response.json()
            covers = item.get('covers', [])
            return {
                'id': book_id,
                'source': 'openlibrary',
                'title': item.get('title', 'Unknown title'),
                'author': 'Open Library',
                'description': 'No description available.',
                'thumbnail': f'https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg' if covers else '',
                'isbn': None,
            }

        response = await client.get(f'{GOOGLE_BOOKS_URL}/{book_id}')
        if response.status_code == 404:
            return None
        response.raise_for_status()
        item = response.json()

    volume = item.get('volumeInfo', {})
    image_links = volume.get('imageLinks', {})
    return {
        'id': item.get('id'),
        'source': 'google',
        'title': volume.get('title', 'Unknown title'),
        'author': ', '.join(volume.get('authors', [])) if volume.get('authors') else 'Unknown author',
        'description': volume.get('description', 'No description available.'),
        'thumbnail': image_links.get('thumbnail') or image_links.get('smallThumbnail') or '',
        'isbn': _pick_isbn(volume.get('industryIdentifiers')),
    }
