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


def register_target(title, id):
    return db['targets'].insert({'title': title, 'telegram_id': id})


def add_admin(username, telegram_id):
    return db['admins'].insert({
        'username': username,
        'telegram_id': telegram_id
    })


def export_download_links():
    links = [
        row.download_url for row in db['found_books'].find(processed=False)
    ]
    open('links.txt',
         'a').write('\n' + '\n'.join(links).replace(' ', '%20') + '\n')
    for row in db['found_books'].find(processed=False):
        row['processed'] = True
        db['found_books'].update(row, ['id'])
