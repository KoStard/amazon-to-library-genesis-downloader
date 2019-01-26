import re
from telegram_api import Bot
import dataset
from stuf import stuf
from algen import algen
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)

bot_data = db['private_data'].find_one(selected=True)


def offset_handler(new_offset):
    bot_data.offset = new_offset
    db['private_data'].update(bot_data, ['id'])


bot = Bot(
    token=bot_data.token,
    offset=bot_data.offset,
    offset_handler=offset_handler)

running = True
while running:
    updates = bot.update()
    for update in updates:
        message = update['message']
        chat = message['chat']
        text = message.get('text')
        if not text:
            continue
        if text[0] == '/':
            print("Got command")
            continue
        text = re.sub(r'\s{2,}', ' ', text.strip())
        if len(text) < 10 or ' ' not in text:
            print("Invalid query \"{}\"".format(text))
            bot.send_message(
                chat['id'],
                "Invalid query. The query has to be longer than 9 characters and contain both the book name and author name. For more contact with @KoStard",
                reply_to_message_id=message['message_id'])
            continue
        info = algen(
            text,
            db,
            user_id=message['from']['id'],
            user_name=' '.join(
                filter(
                    None, message['from'].get('first_name')
                    or message['from'].get('username'),
                    +message['from'].get('last_name'))))
        print("Added {}".format(info['title']))
        bot.send_message(
            chat['id'],
            "Added book {} - {} from {}".format(
                info['title'], info['authors'].split('|')[0], ' '.join(
                    filter(
                        None, message['from'].get('first_name')
                        or message['from'].get('username'),
                        +message['from'].get('last_name')))),
            reply_to_message_id=message['message_id'])
