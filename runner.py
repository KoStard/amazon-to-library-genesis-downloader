from telegram_api import Bot
import dataset
from stuf import stuf
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)

bot_data = db['private_data'].find_one(selected=True)


def offset_handler(new_offset):
    bot_data.offset = new_offset
    db['private_data'].update(bot_data, ['id'])


bot = Bot(
    token=bot_data.token,
    offset=bot_data.offset,
    offset_handler=offset_handler)


def update_bot(bot):
    bot.update()


update_bot(bot)