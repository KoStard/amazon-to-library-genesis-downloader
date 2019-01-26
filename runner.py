import re
from telegram_api import Bot
import dataset
from stuf import stuf
from algen import algen
import controller
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)

bot_data = db['bots'].find_one(selected=True)


def create_book_caption(book):
    return ' - '.join(
        filter(None, [
            book.title, book.year, ', '.join(book.authors.split('|')[:2]),
            book.series, book.publisher
        ]))


def publish(bot, chat_id, book):
    if book.cover_image:
        bot.send_image(
            chat_id, open(book.cover_image), caption=create_book_caption(book))
        bot.send_document(chat_id, book.telegram_file_id)
    else:
        bot.send_document(
            chat_id, book.telegram_file_id, caption=create_book_caption(book))


def offset_setter(new_offset):
    bot_data.offset = new_offset
    db['bots'].update(bot_data, ['id'])


def offset_handler():
    return bot_data.offset


bot = Bot(token=bot_data.token, offset_handler=offset_handler)

running = True
while running:
    try:
        updates = bot.update()
        last_update = None
        for update in updates:
            print(update)
            if last_update: offset_handler(last_update['update_id'] + 1)
            last_update = update
            message = update['message']
            chat = message['chat']
            raw_text = message.get('text') or ''
            for text in raw_text.split('\n'):
                if not text:
                    continue
                if text[0] == '/':
                    print("Got command {}".format(text))
                    if db['admins'].find_one(
                            telegram_id=message['from']['id']):
                        if text == '/register':
                            controller.register_target(
                                message['chat'].get('title')
                                or message['chat'].get('username'),
                                message['chat']['id'])
                        elif text == 'publish':
                            chat_id = db['targets'].find_one().id
                            books = db['found_books'].find(
                                file_found=True, published=False)
                            for book in books:
                                publish(bot, chat_id, book)
                    continue
                text = re.sub(r'\s{2,}', ' ', text.strip())
                if len(text) < 10 or ' ' not in text:
                    print("Invalid query \"{}\"".format(text))
                    bot.send_message(
                        chat['id'],
                        "Invalid query. The query has to be longer than 9 characters and contain both the book name and author name.\nFor more information contact with @KoStard",
                        reply_to_message_id=message['message_id'])
                    continue
                info = algen(
                    text,
                    db,
                    user_id=message['from']['id'],
                    user_name=' '.join(
                        filter(None, (message['from'].get('first_name')
                                      or message['from'].get('username'),
                                      message['from'].get('last_name')))))
                if info['done']:
                    info = info['info']
                    print("Added {}".format(info['title']))
                    bot.send_message(
                        chat['id'],
                        "Added book {}\nFrom: {}\nIt will be published into the channel soon - @MedStard_Books."
                        .format(
                            ' - '.join(
                                filter(None, (info['title'],
                                              info['authors'].split('|')[0],
                                              str(info['year'])))),
                            ' '.join(
                                filter(None,
                                       (message['from'].get('first_name')
                                        or message['from'].get('username'),
                                        message['from'].get('last_name'))))),
                        reply_to_message_id=message['message_id'])
                elif info.get('cause'):
                    bot.send_message(
                        chat['id'],
                        info['cause'],
                        reply_to_message_id=message['message_id'])
            if 'document' in message:
                if not db['admins'].find_one(
                        telegram_id=message['from']['id']):
                    bot.send_message(
                        chat['id'],
                        "You can't send documents to the bot, if you want to publish books in the channel too, then contact with @KoStard",
                        reply_to_message_id=message['message_id'])
                    continue
                document = message['document']
                filename = document.get('file_name')
                file_id = document['file_id']
                book = db['found_books'].find_one(
                    processed=True, telegram_file_id='', filename=filename)
                if book:
                    book.telegram_file_id = file_id
                    book.file_found = True
                    db['found_books'].update(book, ['id'])
                    bot.send_message(
                        chat['id'],
                        "The file is bound with {} - {} - {}".format(
                            book.title, book.authors.replace('|', ', '),
                            book.year),
                        reply_to_message_id=message['message_id'])
                else:
                    bot.send_message(
                        chat['id'],
                        "Can't find any book with name {}".format(filename),
                        reply_to_message_id=message['message_id'])
        if last_update: offset_setter(last_update['update_id'] + 1)
    except:
        print("Error")
        pass
