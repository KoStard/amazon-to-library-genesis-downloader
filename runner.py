import re
from telegram_api import Bot
import dataset
from stuf import stuf
from algen import algen, add_invalid_query, add_from_md5
import controller
import logging
from time import sleep
from datetime import datetime
db = dataset.connect('sqlite:///books_data.db', row_type=stuf)

bot_data = db['bots'].find_one(selected=True)

tags = [
    "Anatomy", "Physiology", "Anesthesiology", "Intensive Care", "Cardiology",
    "Chinese", "Clinical", "Dentistry", "Orthodontics", "Diabetes",
    "Internal Medicine", "Diseases", "Endocrinology", "ENT", "Epidemiology",
    "Feng Shui", "Histology", "Homeopathy", "Immunology", "Infectious",
    "Molecular", "Natural", "Neurology", "Oncology", "Ophthalmology",
    "Pediatrics", "Pharmacology", "Surgery", "Orthopedics", "Therapy", "Trial",
    "Yoga", "Anthropology", "Evolution", "Biostatistics", "Biotechnology",
    "Biophysics", "Biochemistry", "Chemistry", "Ecology", "Genetics",
    "Microbiology", "Biology", "Virology", "Zoology", "Pathology"
]


def configure_logging():
    """ Encoding will be utf-8 """
    root_logger = logging.getLogger()
    """ Preventing multiple calls """
    if (root_logger.handlers
            and root_logger.handlers[0].stream.name == "logs.txt"
            and root_logger.handlers[0].stream.encoding == "utf-8"):
        return
    root_logger.setLevel(logging.INFO)
    handler = logging.FileHandler("logs.txt", "a", "utf-8")
    root_logger.addHandler(handler)


configure_logging()


def create_book_caption(book):
    return re.sub(
        r'([\\/|:*?"\’<>]|[^[:ascii:]])', '', ' - '.join(
            filter(None, [
                book.title + (' ' + book.version if book.version else ''),
                str(book.year), ', '.join(book.authors.split('|')[:2]),
                book.series, book.publisher
            ])) + '\n' +
        ' '.join([
            '#' + hashtag.replace(' ', '_').replace('-', '').replace('.', '')
            for hashtag in filter(None, [
                book.series, book.publisher,
                book.authors.split('|')[0].split(' ')[0]
            ] + [
                tag
                for tag in tags if re.search(
                    r'(^|\s)' + tag.lower() + r'(\s|$)', book.title.lower())
            ])
        ]))


def publish(bot, chat_id, book):
    if book.cover_image:
        bot.send_image(
            chat_id,
            open(book.cover_image, 'rb'),
            caption=create_book_caption(book))
        bot.send_document(chat_id, book.telegram_file_id)
    else:
        bot.send_document(
            chat_id, book.telegram_file_id, caption=create_book_caption(book))
    book.published = True
    book.publication_day_of_year = datetime.now().timetuple().tm_yday
    db['found_books'].update(book, ['id'])


def offset_setter(new_offset):
    bot_data.offset = new_offset
    db['bots'].update(bot_data, ['id'])


def offset_handler():
    return bot_data.offset


bot = Bot(token=bot_data.token, offset_handler=offset_handler)
print("Running")
running = True
while running:
    if True:
        # try:
        updates = bot.update()
        last_update = None
        for update in updates:
            print(update)
            logging.info(update)
            if last_update: offset_setter(last_update['update_id'] + 1)
            last_update = update
            message = update['message']
            chat = message['chat']
            raw_text = message.get('text') or ''
            for text in raw_text.split('\n'):
                if not text:
                    continue
                if text == 'Operative Thoracic Surgery':
                    continue
                sleep(1)
                print("Processing ", text)
                if text[0] == '/':
                    text = text.split('@')[0]
                    print("Got command {} from {}".format(
                        text, message['from'].get('first_name')
                        or message['from'].get('username')
                        or message['from'].get('last_name')))
                    logging.info("Got command {} from {}".format(
                        text, message['from'].get('first_name')
                        or message['from'].get('username')
                        or message['from'].get('last_name')))
                    if db['super_admins'].find_one(
                            telegram_id=message['from']['id']) or text == '/start':
                        if text == '/register':
                            controller.register_target(
                                message['chat'].get('title')
                                or message['chat'].get('username'),
                                message['chat']['id'])
                            bot.send_message(
                                message['chat']['id'],
                                "This target is now registered, now you can publish books here with /publish.",
                                reply_to_message_id=message['message_id'])
                        elif text == '/publish':
                            chat_id = db['targets'].find_one(id=2).telegram_id
                            books = db['found_books'].find(
                                file_found=True, published=False)
                            for book in books:
                                publish(bot, chat_id, book)
                        elif text == '/register_admin':
                            user = message['forward_from']
                            if user:
                                db['admins'].insert({
                                    'username': user.get('username') or user.get('first_name') or user.get('last_name'),
                                    'telegram_id': user['id']
                                })
                                bot.send_message(
                                    message['chat']['id'],
                                    "User {} is now registered as an admin.".
                                    format(
                                        user.get('username')
                                        or user.get('first_name')
                                        or user.get('last_name')), reply_to_message_id=message['message_id'])
                        elif text == '/start':
                            bot.send_message(
                                message['chat']['id'],
                                "Just send me full name of the book and first name of the author and I'll find the book for you ;)...\nThe query has to be longer than 9 characters, shorter than 81 characters and contain both the book name and author name - only English is supported.",
                                reply_to_message_id=message['message_id'])
                    continue
                text = re.sub(r'[^[:ascii:]]+', ' ')
                text = re.sub(r'\s{2,}', ' ', text.strip())
                if len(text) < 10 or len(
                        text) > 80 or ' ' not in text:
                    print("Invalid query \"{}\" from {}".format(
                        text, message['from'].get('first_name')
                        or message['from'].get('username')
                        or message['from'].get('last_name')))
                    logging.info("Invalid query \"{}\" from {}".format(
                        text, message['from'].get('first_name')
                        or message['from'].get('username')
                        or message['from'].get('last_name')))
                    print("Will send message")
                    bot.send_message(
                        chat['id'],
                        "Invalid query. The query has to be longer than 9 characters, shorter than 81 characters and contain both the book name and author name - only English is supported.\nFor more information contact with @KoStard",
                        reply_to_message_id=message['message_id'])
                    continue
                print("Before algen", text)
                try:
                    if text[0] == '*':
                        info = add_from_md5(
                            text[1:],
                            db,
                            user_id=message['from']['id'],
                            user_name=' '.join(
                                filter(None,
                                       (message['from'].get('first_name')
                                        or message['from'].get('username'),
                                        message['from'].get('last_name')))))
                    else:
                        info = algen(
                            text,
                            db,
                            user_id=message['from']['id'],
                            user_name=' '.join(
                                filter(None, (message['from'].get('first_name')
                                            or message['from'].get('username'),
                                            message['from'].get('last_name')))))
                except Exception as e:
                    logging.info(e)
                    print(e)
                    add_invalid_query({
                        "query": text
                    }, db, message['from']['id'], ' '.join(
                        filter(None, (message['from'].get('first_name')
                                      or message['from'].get('username'),
                                      message['from'].get('last_name')))))
                    bot.send_message(
                        chat['id'],
                        "The bot can't search that query, it will be supervised by MedStard's team.\nFor more contact with @KoStard",
                        reply_to_message_id=message['message_id'])
                    continue
                print("After algen")
                if info['done']:
                    info = info['info']
                    print("Added {} from {}".format(info['title'],
                                                    info['user_name']))
                    logging.info("Added {} from {}".format(
                        info['title'], info['user_name']))
                    if info['cover_image']:
                        bot.send_image(
                            chat['id'],
                            open(info['cover_image'], 'rb'),
                            reply_to_message_id=message['message_id'],
                            caption=
                            "Added book {}\nFrom: {}\nIt will be published into the channel soon - @MedStard_Books."
                            .format(
                                ' - '.join(
                                    filter(None,
                                           (info['title'],
                                            info['authors'].split('|')[0],
                                            str(info['year'])))),
                                ' '.join(
                                    filter(
                                        None,
                                        (message['from'].get('first_name')
                                         or message['from'].get('username'),
                                         message['from'].get('last_name'))))))
                    else:
                        bot.send_message(
                            chat['id'],
                            "Added book {}\nFrom: {}\nIt will be published into the channel soon - @MedStard_Books."
                            .format(
                                ' - '.join(
                                    filter(None,
                                           (info['title'],
                                            info['authors'].split('|')[0],
                                            str(info['year'] or '')))),
                                ' '.join(
                                    filter(
                                        None,
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
                book = [
                    b for b in db['found_books'].find(file_found=False)
                    if b.filename == filename
                    or '.'.join(filename.split('.')
                                [:-1]) in b.filename.replace(' - ','').replace(' ', '_')
                ]
                if book:
                    book = book[0]
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
    # except Exception as e:
    #     print("Error", e)
    #     logging.info(e)
    #     pass
