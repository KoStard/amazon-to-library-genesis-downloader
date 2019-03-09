import re
from telegram_api import Bot
import dataset
from stuf import stuf
from algen import algen, add_invalid_query, add_from_md5
import controller
import logging
from time import sleep
from datetime import datetime
import os
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
    if (root_logger.handlers and
            root_logger.handlers[0].stream.name == "logs.txt" and
            root_logger.handlers[0].stream.encoding == "utf-8"):
        return
    root_logger.setLevel(logging.INFO)
    handler = logging.FileHandler("logs.txt", "a", "utf-8")
    root_logger.addHandler(handler)


configure_logging()


def log_to_admpage(text, *, sub=False):
    if db['administrator_page'].count():
        bot.send_message(db['administrator_page'].find_one().telegram_id,
                         "{} {}".format('|=>' if not sub else '└', text))


def create_book_caption(book):
    return re.sub(
        r'([\\/|:*?"\’<>]|[^[:ascii:]])', '', ' - '.join(
            filter(None, [
                book.title + (' ' + book.version if book.version else ''),
                str(book.year or ''), ', '.join(book.authors.split('|')[:2]),
                book.series, book.publisher
            ])) + '\n' +
        ' '.join([
            ht for ht in ('#' + re.sub(r'([-.$,&;\'"]|\([^)+]\))', '',
                                       re.sub(r'\s+', '_', hashtag.strip()))
                          for hashtag in filter(None, [
                              book.series, book.publisher,
                              book.authors.split('|')[0].split(' ')[0]
                          ] + [
                              tag
                              for tag in tags
                              if re.search(r'(^|\s)' + tag.lower() +
                                           r'(\s|$)', book.title.lower())
                          ])) if len(ht) >= 3
        ]))


def publish(bot, chat_id, book):
    if book.cover_image:
        resp = bot.send_image(
            chat_id,
            open(book.cover_image, 'rb'),
            caption=create_book_caption(book),
            silent=True)
        if resp:
            bot.send_document_by_file_id(
                chat_id, book.telegram_file_id, silent=True)
        else:
            bot.send_document_by_file_id(
                chat_id,
                book.telegram_file_id,
                caption=create_book_caption(book),
                silent=True)
    else:
        bot.send_document_by_file_id(
            chat_id,
            book.telegram_file_id,
            caption=create_book_caption(book),
            silent=True)
    book.published = True
    book.publication_day_of_year = datetime.now().timetuple().tm_yday
    db['found_books'].update(book, ['id'])


def get_unique_name(filename):
    dirname = os.path.dirname(filename)
    filename = filename[len(dirname) + (1 if dirname else 0):]
    content = os.listdir(dirname or None)
    if filename in content:
        if '.' in filename:
            name = '.'.join(filename.split('.')[:-1])
            ext = filename[len(name) + (1 if name else 0):]
        else:
            name = filename
            ext = ''
        i = 1
        while '{}-{}.{}'.format(name, i, ext) in content:
            i += 1
        return dirname + ('/' if dirname else '') + '{}-{}.{}'.format(
            name, i, ext)
    else:
        return dirname + ('/' if dirname else '') + filename


def offset_setter(new_offset):
    bot_data.offset = new_offset
    db['bots'].update(bot_data, ['id'])


def offset_handler():
    return bot_data.offset


bot = Bot(token=bot_data.token, offset_handler=offset_handler)
print("Running")
running = True
while running:
    # if True:
    try:
        updates = bot.update()
        last_update = None
        for update in updates:
            logging.info(update)
            if last_update: offset_setter(last_update['update_id'] + 1)
            last_update = update
            if not 'message' in update:
                continue
            message = update['message']
            chat = message['chat']
            from_name = message['from'].get('first_name') or message[
                'from'].get('username') or message['from'].get('last_name')
            raw_text = (message.get('text') or '').split('\n')
            for text in raw_text:
                if not text:
                    continue
                # if text[0] != '/':
                #     bot.send_message(chat['id'], 'Sorry, but the bot is now closed and I don\'t know when it will be reopened.', reply_to_message_id=message['message_id'])
                #     continue
                if db['administrator_page'].find_one(telegram_id=chat['id']):
                    pass  #- In the administrator page
                else:
                    log_to_admpage('{} => {}'.format(from_name, text))
                    sleep(1)
                    print("Processing ", text)
                    if text[0] == '/':
                        text = text.split('@')[0]
                        print("Got command {} from {}".format(text, from_name))
                        logging.info("Got command {} from {}".format(
                            text, from_name))
                        if db['super_admin'].find_one(
                                telegram_id=message['from']
                            ['id']) or text == '/start':
                            if text == '/register':
                                controller.register_target(
                                    message['chat'].get('title') or
                                    message['chat'].get('username'),
                                    message['chat']['id'])
                                bot.send_message(
                                    message['chat']['id'],
                                    "This target is now registered, now you can publish books here with /publish.",
                                    reply_to_message_id=message['message_id'])
                            if text == '/register_administrator_page':
                                controller.register_administrator_page(
                                    message['chat']['title'],
                                    message['chat']['id'])
                                bot.send_message(
                                    message['chat']['id'],
                                    "This target is now registered as an administrator page, now you'll get logs here.",
                                    reply_to_message_id=message['message_id'])
                            elif text == '/publish':
                                chat_id = db['targets'].find_one(
                                    id=2).telegram_id
                                books = db['found_books'].find(
                                    file_found=True, published=False)
                                for book in books:
                                    publish(bot, chat_id, book)
                            elif text == '/register_admin':
                                user = message['forward_from']
                                if user:
                                    db['admins'].insert({
                                        'username': user.get('username')
                                                    or user.get('first_name')
                                                    or user.get('last_name'),
                                        'telegram_id': user['id']
                                    })
                                    bot.send_message(
                                        message['chat']['id'],
                                        "User {} is now registered as an admin."
                                        .format(
                                            user.get('username') or
                                            user.get('first_name') or
                                            user.get('last_name')),
                                        reply_to_message_id=message[
                                            'message_id'])
                            elif text == '/start':
                                print("Sending start command response")
                                bot.send_message(
                                    message['chat']['id'],
                                    "Just send me full name of the book and first name of the author and I'll find the book for you ;)...\nThe query has to be longer than 9 characters, shorter than 81 characters and contain both the book name and author name - only English is supported.",
                                    reply_to_message_id=message['message_id'])
                            elif text == '/export_download_links':
                                links_file_name = get_unique_name(
                                    'exported_links.txt')
                                controller.export_download_links(
                                    links_file_name)
                                try:
                                    bot.send_document(
                                        message['chat']['id'],
                                        open(links_file_name, 'rb'))
                                except Exception as e:
                                    print(e)
                        continue
                    text = re.sub(r'[^[:ascii:]]+', ' ', text)
                    text = re.sub(r'\s{2,}', ' ', text.strip())
                    MIN_LENGTH = 10
                    MAX_LENGTH = 80
                    if text[0] != '*' and (len(text) < MIN_LENGTH or
                                           len(text) > MAX_LENGTH or
                                           ' ' not in text):
                        print("Invalid query \"{}\" from {}".format(
                            text, message['from'].get('first_name') or
                            message['from'].get('username') or
                            message['from'].get('last_name')))
                        logging.info("Invalid query \"{}\" from {}".format(
                            text, message['from'].get('first_name') or
                            message['from'].get('username') or
                            message['from'].get('last_name')))
                        print("Will send message")
                        cause = ''
                        if len(text) < MIN_LENGTH:
                            cause = 'too short'
                        elif len(text) > MAX_LENGTH:
                            cause = 'too long'
                        elif ' ' not in text:
                            cause = 'the query has to contain multiple words in it'
                        bot.send_message(
                            chat['id'],
                            "Invalid query - {cause}.\nThe query has to be longer than 9 characters, shorter than 81 characters and contain both the book name and author name - only English is supported.\nFor more information contact with @KoStard"
                            .format(cause=cause),
                            reply_to_message_id=message['message_id'])
                        continue
                    print("Before algen", text)
                    MODE = "link"
                    try:
                        if text[0] == '*':
                            info = add_from_md5(
                                text[1:],
                                db,
                                user_id=message['from']['id'],
                                user_name=' '.join(
                                    filter(None,
                                           (message['from'].get('first_name') or
                                            message['from'].get('username'),
                                            message['from'].get('last_name')))),
                                mode=MODE)
                        else:
                            info = algen(
                                text,
                                db,
                                user_id=message['from']['id'],
                                user_name=' '.join(
                                    filter(None,
                                           (message['from'].get('first_name') or
                                            message['from'].get('username'),
                                            message['from'].get('last_name')))),
                                mode=MODE)
                    except Exception as e:
                        logging.info(e)
                        print(e)
                        add_invalid_query({
                            "query": text
                        }, db, message['from']['id'], ' '.join(
                            filter(None, (message['from'].get('first_name') or
                                          message['from'].get('username'),
                                          message['from'].get('last_name')))))
                        log_to_admpage("Problem with getting data of the book.")
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
                        log_to_admpage(
                            "N{} - Added {} from {}".format(
                                db['found_books'].count(), info['title'],
                                info['user_name']),
                            sub=True)
                        if info['cover_image']:
                            bot.send_image(
                                chat['id'],
                                open(info['cover_image'], 'rb') if MODE != 'link' else info['cover_image'],
                                reply_to_message_id=message['message_id'],
                                caption=
                                "Added book {}\nFrom: {}\nIt will be published into the channel soon - @MedStard_Books."
                                .format(
                                    ' - '.join(
                                        filter(None,
                                               (info['title'],
                                                info['authors'].split('|')[0],
                                                str(info['year'] or ''),
                                                info['version']))),
                                    ' '.join(
                                        filter(None, (
                                            message['from'].get('first_name') or
                                            message['from'].get('username'),
                                            message['from'].get('last_name')))))
                                if MODE == 'standard' else
                                ('Found book - {}\n<a href="{}">Download</a>'.
                                 format(
                                     ' - '.join(
                                         filter(None,
                                                (info['title'],
                                                 info['authors'].split('|')[0],
                                                 str(info['year'] or ''),
                                                 info['version']))),
                                     info['download_url'])
                                 if MODE == 'link' else ''))
                        else:
                            bot.send_message(
                                chat['id'],
                                "Added book {}\nFrom: {}\nIt will be published into the channel soon - @MedStard_Books."
                                .format(
                                    ' - '.join(
                                        filter(None,
                                               (info['title'],
                                                info['authors'].split('|')[0],
                                                str(info['year'] or ''),
                                                info['version']))),
                                    ' '.join(
                                        filter(None, (
                                            message['from'].get('first_name') or
                                            message['from'].get('username'),
                                            message['from'].get('last_name')))))
                                if MODE == 'standard' else
                                ('Found book - {}\n\\<a href="{}">Download\\</a>'.
                                 format(
                                     ' - '.join(
                                         filter(None,
                                                (info['title'],
                                                 info['authors'].split('|')[0],
                                                 str(info['year'] or ''),
                                                 info['version']))),
                                     info['download_url'])
                                 if MODE == 'link' else ''),
                                reply_to_message_id=message['message_id'])
                    elif info.get('cause'):
                        bot.send_message(
                            chat['id'],
                            info['cause'],
                            reply_to_message_id=message['message_id'])
                        log_to_admpage(info['cause'])
            if len(raw_text) > 1:
                bot.send_message(
                    chat['id'],
                    'Finished processing of this message.',
                    reply_to_message_id=message['message_id'])
            if 'document' in message:
                if not db['admins'].find_one(telegram_id=message['from']['id']):
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
                    if b.filename == filename or
                    '.'.join(filename.split('.')[:-1]) == re.sub(
                        r'\s+', '_', b.filename.replace(
                            '-', ' '))[:len('.'.join(filename.split('.')[:-1]))]
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
    except Exception as e:
        print("Error", e)
        logging.info(e)
        pass
