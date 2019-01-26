import dataset
from stuf import stuf
import requests
import re
from bs4 import BeautifulSoup

headers = {
    'User-Agent':
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36'
}

db = dataset.connect('sqlite:///books_data.db', row_type=stuf)


def algen(query):
    """ Just give search query and the program will search and
    give you the link, details and the cover of the newest version """
    if not query: return
    content = find(query)
    if not content: return
    md5 = get_md5(content, query)
    if not md5 or db['found_books'].find(md5=info['md5']): return
    info = load_book_info(md5, query)
    if not info: return
    durl = convert_download_url(info)
    if not durl: return
    download_cover_image(info)
    save_book_info(info)


def find(query):
    url = 'http://gen.lib.rus.ec/search.php?&req={query}&phrase=1&view=simple&column=def&sort=year&sortmode=DESC'.format(
        query=query)
    page = requests.get(url, headers)
    if not page.ok:
        print("Can't search")
        add_invalid_query({"query": query})
        return
    return page.content


def get_md5(content, query):
    s = BeautifulSoup(content)
    tables = s.find_all('table')
    results_number = int(tables[1].tr.td.font.text.split()[0])
    if results_number:
        path = tables[2].findChildren('tr')[1].findChildren(
            'td')[2].findChildren('a')[1].attrs['href']
        md5 = re.search(r'md5=([^&/]+)', path)
        if md5:
            md5 = md5.group(1)
            return md5
    else:
        print("Can't find book with query {}".format(query))
        add_invalid_query({"query": query})
        return


def load_book_info(md5, query):
    url = 'http://lib1.org/_ads/{md5}'.format(md5=md5)
    page = requests.get(url, headers)
    if not page.ok:
        print("Not OK in the load_book_info")
        add_invalid_query({"query": query, "found_url": url})
        return
    page_bs = BeautifulSoup(page.content)
    info = page_bs.find(id='info')
    info_children = info.find_all(recursive=False)

    res = {
        'query': query,
        'processed': False,
        'filename': '',
        'download_url': '',
        'image_url': '',
        'has_cover': False,
        'title': '',
        'authors': [],
        'series': '',
        'publisher': '',
        'year': None,
        'md5': md5,
        'telegram_file_id': '',
    }

    for child in info_children:
        tag = child.name
        if tag == 'h2':
            res['download_url'] = child.a.attrs['href']
        elif tag == 'div':
            if child.img:
                url = child.img.attrs['src']
                res['image_url'] = url if url != '/img/blank.png' else None
            #- Description or image here
        elif tag == 'h1':
            res['title'] = child.text
        elif tag == 'p':
            text = child.text
            if ': ' in text:
                if text.count(': ') == 1:
                    marker, content, *args = text.split(': ')
                    if marker == 'Author(s)':
                        res['authors'] = content.split(', ')
                    elif marker == 'Series':
                        res['series'] = content
                else:
                    marker, content, year_t, *args = text.split(': ')
                    if marker == 'Publisher':
                        res['publisher'] = ', '.join(content.split(', ')[:-1])
                        res['year'] = int(year_t)
        else:
            pass
    return res


def create_filename_base(info):
    """ The max length is 60 """
    return ' - '.join(
        filter(None,
               (info['title'], info['authors'][0], str(info['year']))))[:60]


def convert_download_url(info):
    base = '/'.join(info['download_url'].split('/')[:-1])
    ext = info['download_url'].split('/')[-1].split('.')
    if len(ext) == 1:
        print("Invalid filename {}".format(
            info['download_url'].split('/')[-1]))
        add_invalid_query({
            "query": info['query'],
            "found_url": info['download_url']
        })
        return
    ext = ext[-1]
    filename_base = create_filename_base(info)
    filename = filename_base + '.' + ext
    if db['found_books'].find(filename='{}.{}'.format(filename_base, ext)):
        index = 2
        while db['found_books'].find(
                filename='{} ({}).{}'.format(filename_base, index, ext)):
            index += 1
        filename = '{} ({}).{}'.format(filename_base, index, ext)
    info['filename'] = filename
    info['download_url'] = base + '/' + filename
    return info['download_url']


def download_cover_image(info):
    if info['image_url']:
        info['image_url'] = 'http://gen.lib.rus.ec' + info['image_url']
        resp = requests.get(info['image_url'], headers)
        if resp.ok:
            open(
                'covers/{base}_cover.{ext}'.format(
                    base='.'.join(info['filename'].split('.')[:-1]),
                    ext=info['image_url'].split('.')[-1]),
                'wb').write(resp.content)
            info['has_cover'] = True


def save_book_info(info):
    found_books = db['found_books']
    if found_books.find(md5=info['md5']):
        pass
    info['authors'] = '|'.join(info['authors'])
    found_books.insert(info)


def add_invalid_query(data):
    """ {query} or {query, found_url} """
    if not db['invalid_queries'].find(query=data['query']):
        db['invalid_queries'].insert(data)
