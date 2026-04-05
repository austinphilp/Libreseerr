from __future__ import annotations

import httpx

GOOGLE_BOOKS_URL = 'https://www.googleapis.com/books/v1/volumes'
OPEN_LIBRARY_URL = 'https://openlibrary.org/search.json'
OPEN_LIBRARY_WORK_URL = 'https://openlibrary.org'


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
            response = await client.get(OPEN_LIBRARY_URL, params={'q': query, 'limit': 20, 'fields': 'key,title,author_name,first_sentence,cover_i,isbn'})
            response.raise_for_status()
            data = response.json()
            return _parse_open_library(data)


def _normalize_description(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        return str(value.get('value') or '').strip() or 'No description available.'
    if isinstance(value, list) and value:
        return _normalize_description(value[0])
    return 'No description available.'


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
            'description': _normalize_description(volume.get('description')),
            'thumbnail': image_links.get('thumbnail') or image_links.get('smallThumbnail') or '',
            'isbn': _pick_isbn(volume.get('industryIdentifiers')),
        })
    return results


def _parse_open_library(data: dict) -> list[dict]:
    results = []
    for item in data.get('docs', []):
        cover = item.get('cover_i')
        isbn = item.get('isbn', [None])[0] if item.get('isbn') else None
        key = item.get('key', '')
        description = _normalize_description(item.get('first_sentence'))
        if description == 'No description available.' and key:
            description = f'Open Library entry for {item.get("title", "Unknown title")}.'
        results.append({
            'id': key.removeprefix('/works/'),
            'source': 'openlibrary',
            'title': item.get('title', 'Unknown title'),
            'author': ', '.join(item.get('author_name', [])) if item.get('author_name') else 'Unknown author',
            'description': description,
            'thumbnail': f'https://covers.openlibrary.org/b/id/{cover}-L.jpg' if cover else '',
            'isbn': isbn,
        })
    return results


async def get_book(book_id: str, source: str = 'google') -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        if source == 'openlibrary':
            response = await client.get(f'{OPEN_LIBRARY_WORK_URL}/works/{book_id}.json')
            if response.status_code == 404:
                return None
            response.raise_for_status()
            item = response.json()
            covers = item.get('covers', [])
            description = _normalize_description(item.get('description'))
            if description == 'No description available.':
                description = f'Open Library entry for {item.get("title", "Unknown title")}.'
            return {
                'id': book_id,
                'source': 'openlibrary',
                'title': item.get('title', 'Unknown title'),
                'author': 'Open Library',
                'description': description,
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
        'description': _normalize_description(volume.get('description')),
        'thumbnail': image_links.get('thumbnail') or image_links.get('smallThumbnail') or '',
        'isbn': _pick_isbn(volume.get('industryIdentifiers')),
    }
