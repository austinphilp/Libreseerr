from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .metadata import get_book, search_books
from .readarr import ReadarrClient

app = FastAPI(title='Libreseerr')
templates = Jinja2Templates(directory='app/templates')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/', response_class=HTMLResponse)
async def home(request: Request, q: str = ''):
    settings = get_settings()
    results = []
    if q:
        try:
            results = await search_books(q)
        except Exception:
            results = []
    return templates.TemplateResponse('index.html', {'request': request, 'settings': settings, 'targets': settings.targets(), 'query': q, 'results': results})


@app.get('/book/{source}/{book_id}', response_class=HTMLResponse)
async def book_detail(request: Request, source: str, book_id: str):
    settings = get_settings()
    book = await get_book(book_id, source=source)
    if book is None:
        raise HTTPException(status_code=404, detail='Book not found')
    return templates.TemplateResponse('book.html', {'request': request, 'settings': settings, 'targets': settings.targets(), 'book': book, 'message': None, 'error': None})


@app.post('/request', response_class=HTMLResponse)
async def request_book(request: Request, title: str = Form(...), author: str = Form(...), target_name: str = Form(...), goodreads_id: str | None = Form(default=None), source: str = Form(default='google'), book_id: str = Form(default='')):
    settings = get_settings()
    target = next((t for t in settings.targets() if t.name == target_name), None)
    if target is None:
        raise HTTPException(status_code=404, detail='Readarr target not found')
    client = ReadarrClient(target)
    message = None
    error = None
    try:
        message = await client.request_book(title=title, author=author, goodreads_id=goodreads_id)
    except Exception as exc:
        error = str(exc)
    book = {'id': book_id, 'source': source, 'title': title, 'author': author, 'description': '', 'thumbnail': '', 'isbn': goodreads_id}
    return templates.TemplateResponse('book.html', {'request': request, 'settings': settings, 'targets': settings.targets(), 'book': book, 'message': message, 'error': error})
