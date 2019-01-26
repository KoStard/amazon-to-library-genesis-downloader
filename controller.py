from telegram_api import Bot
import dataset
from stuf import stuf
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)


def add_bot(token):
    bot = Bot(token, 0)
    name = bot.name
    return db['private_data'].insert({
        'name': name,
        'token': token,
        'offset': 0,
        'selected': True,
    })
