from telegram_api import Bot
import dataset
from stuf import stuf
import os
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)


def add_bot(token):
    bot = Bot(token, 0)
    name = bot.name
    return db['bots'].insert({
        'name': name,
        'token': token,
        'offset': 0,
        'selected': True,
    })


def add_admin(username, telegram_id):
    return db['admins'].insert({
        'username': username,
        'telegram_id': telegram_id
    })


def export_download_links():
    links = [
        row.download_url for row in db['found_books'].find_all(processed=False)
    ]
    open('links.txt', 'w').write('\n'.join(links))
    for row in db['found_books'].find_all(processed=False):
        row['processed'] = True
        db['found_books'].update(row, ['id'])


def publish():
    """ Will post the non-posted books """
    #- Can't get tags yet - they are in the main page of the book
    pass