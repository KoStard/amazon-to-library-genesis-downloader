from telegram_api import Bot
from private_data import token
bot = Bot(token=token)
del token


def update_bot(bot):
    bot.update()


update_bot(bot)