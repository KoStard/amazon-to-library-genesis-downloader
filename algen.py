import dataset
from stuf import stuf
import requests
import re
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36'
}


def algen(query, db, user_id=None, user_name=None, mode='standard'):
    """ Just give search query and the program will search and
    give you the link, details and the cover of the newest version """
    if not query: return {"done": False}
    content = find(query, db, user_id, user_name)
    if not content: return {"done": False}
    md5 = get_md5(content, query, db, user_id, user_name)
    if not md5:
        return {
            "done": False,
            "cause":
                "Can't find book {}, it will be supervised by MedStard's team.".
                format(query)
        }
    found_book = db['found_books'].find_one(md5=md5)
    if found_book and mode == 'standard':
        print("Already Found")
        return {
            "done": False,
            "cause": "Book {} was already added - {}".format(
                found_book.title,
                'it should already be published' if found_book.processed else
                'it will be published into the channel soon - @MedStard_Books')
        }
    info = load_book_info(md5, query, db, user_id, user_name)
    if not info: return {"done": False}
    load_book_version(info)
    durl = convert_download_url(info, db, user_id, user_name)
    if not durl: return {"done": False}
    download_cover_image(info, db, user_id, user_name)
    if mode == 'standard':
        save_book_info(info, db, user_id, user_name)
    return {"done": True, "info": info}


def find(query, db, user_id, user_name):
    url = 'http://gen.lib.rus.ec/search.php?&req={query}&phrase=1&view=simple&column=def&sort=year&sortmode=DESC'.format(
        query=query)
    page = requests.get(url, headers)
    if not page.ok:
        print("Can't search")
        add_invalid_query({"query": query}, db, user_id, user_name)
        return
    return page.content


def get_md5(content, query, db, user_id, user_name):
    s = BeautifulSoup(content, 'html.parser')
    tables = s.find_all('table')
    results_number = int(tables[1].tr.td.font.text.split()[0])
    if results_number:
        row_index = 1
        rows = tables[2].findChildren('tr')
        while rows[row_index].findChildren('td')[8].text != 'pdf':
            print("Found another format, will look at next row")
            row_index += 1
            if row_index == len(rows):
                row_index = 1
                break
        row = rows[row_index]
        path = row.findChildren('td')[2].findChildren('a')[-1].attrs['href']
        md5 = re.search(r'md5=([^&/]+)', path)
        if md5:
            md5 = md5.group(1)
            return md5
    else:
        print("Can't find book with query {}".format(query))
        add_invalid_query({"query": query}, db, user_id, user_name)
        return


def load_book_info(md5, query, db, user_id, user_name):
    url = 'http://lib1.org/_ads/{md5}'.format(md5=md5)
    page = requests.get(url, headers)
    if not page.ok:
        print("Not OK in the load_book_info")
        add_invalid_query({
            "query": query,
            "found_url": url
        }, db, user_id, user_name)
        return
    page_bs = BeautifulSoup(page.content, 'html.parser')
    info = page_bs.find(id='info')
    info_children = info.find_all(recursive=False)

    res = {
        'query': query,
        'filename': '',
        'download_url': '',
        'image_url': '',
        'cover_image': '',
        'title': '',
        'version': '',
        'authors': '',
        'series': '',
        'publisher': '',
        'year': None,
        'md5': md5,
        'telegram_file_id': '',
        'processed': False,
        'file_found': False,
        'published': False,
        "publication_day_of_year": None,
        'user_name': user_name,
        'user_id': user_id,
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
                        res['authors'] = '|'.join(content.split(', '))
                    elif marker == 'Series':
                        res['series'] = content
                else:
                    marker, content, year_t, *args = text.split(': ')
                    if marker == 'Publisher':
                        res['publisher'] = ', '.join(content.split(', ')[:-1])
                        res['year'] = int(re.sub('[^\d]', '', year_t))
        else:
            pass
    return res


def load_book_version(info):
    url = 'http://gen.lib.rus.ec/book/bibtex.php?md5={md5}'.format(
        md5=info['md5'])
    page = requests.get(url, headers)
    if not page.ok:
        print("Not OK in the load_book_version")
        return
    page_bs = BeautifulSoup(page.content, 'html.parser')
    text = page_bs.find('textarea').text
    match = re.search('edition\s*=\s*{(.*)}', text)
    if match:
        info['version'] = match.group(1)
        return match.group(1)


def create_filename_base(info):
    """ The max length is 70 """
    return re.sub(
        r'([\\/|:*?"\'’<>]|[^[:ascii:]])', '', ' - '.join(
            filter(
                None,
                (info['title'],
                 (info['authors'].split('|')[0] if info['authors'] else None),
                 str(info['year']))))).strip()[:70]


def convert_download_url(info, db, user_id, user_name):
    base = '/'.join(info['download_url'].split('/')[:-1])
    ext = info['download_url'].split('/')[-1].split('.')
    if len(ext) == 1:
        print("Invalid filename {}".format(info['download_url'].split('/')[-1]))
        add_invalid_query({
            "query": info['query'],
            "found_url": info['download_url']
        }, db, user_id, user_name)
        return
    ext = ext[-1]
    filename_base = create_filename_base(info)
    filename = filename_base + '.' + ext
    # if db['found_books'].find_one(filename='{}.{}'.format(filename_base, ext)):
    #     index = 2
    #     while db['found_books'].find_one(
    #             filename='{} ({}).{}'.format(filename_base, index, ext)):
    #         index += 1
    #     filename = '{} ({}).{}'.format(filename_base, index, ext)
    info['filename'] = filename
    info['download_url'] = base + '/' + filename.replace(' ', '%20')
    return info['download_url']


def download_cover_image(info, db, user_id, user_name):
    if info['image_url']:
        info['image_url'] = 'http://gen.lib.rus.ec' + info['image_url']
        resp = requests.get(info['image_url'], headers)
        if resp.ok:
            cover_filename = 'covers/{base}_cover.{ext}'.format(
                base='.'.join(info['filename'].split('.')[:-1]),
                ext=info['image_url'].split('.')[-1])
            open(cover_filename, 'wb').write(resp.content)
            info['cover_image'] = cover_filename
        else:
            print("Can't download cover image")
            print(resp)


def save_book_info(info, db, user_id, user_name):
    found_books = db['found_books']
    if found_books.find_one(md5=info['md5']):
        pass
    found_books.insert(info)


def add_invalid_query(data, db, user_id, user_name):
    """ {query} or {query, found_url} """
    if not db['invalid_queries'].find_one(query=data['query']):
        db['invalid_queries'].insert(data)


def add_from_md5(md5, db, *, query="", user_id=None, user_name="Admin"):
    found_book = db['found_books'].find_one(md5=md5)
    if found_book:
        print("Already Found")
        return {
            "done": False,
            "cause": "Book {} was already added - {}".format(
                found_book.title,
                'it should already be published' if found_book.processed else
                'it will be published into the channel soon - @MedStard_Books')
        }
    info = load_book_info(md5, query, db, user_id, user_name)
    if not info: return {"done": False}
    load_book_version(info)
    durl = convert_download_url(info, db, user_id, user_name)
    if not durl: return {"done": False}
    download_cover_image(info, db, user_id, user_name)
    save_book_info(info, db, user_id, user_name)
    return {"done": True, "info": info}


if __name__ == '__main__':
    db = dataset.connect('sqlite:///books_data.db', row_type=stuf)
    algen(input('Write query to find: '), db)