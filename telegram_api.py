import json
import requests
import io
import time
MESSAGE_MAX_LENGTH = 4096


def get_response(url, *, payload=None, files=None, use_post=False, raw=False, max_retries=3, timeout=None):
    """ Will get response with get/post based on files existance """
    headers = {"Content-Type": "application/json"}
    if timeout is None:
        if payload is None or 'timeout' not in payload:
            timeout = 10
        else:
            timeout = payload['timeout']*1.5 or 10
    cycle = 0
    while True:
        cycle += 1
        try:
            if files or use_post:
                resp = requests.post(url, params=payload, files=files, timeout=timeout)
            else:
                resp = requests.get(url, params=payload, timeout=timeout)
            break
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            if cycle >= max_retries:
                time.sleep(2)  # Will always try to connect
                print("Trying to reconnect...")
    data = resp.json()
    if resp.status_code == 200:
        if raw:
            return resp.content
        return data.get("result") if data.get("result") is not None else data
    elif data.get('error_code') == 400:
        if data.get('description') == 'Bad Request: reply message not found':
            del payload['reply_to_message_id']  # Sending the message without replying
            return get_response(url,
                                payload=payload,
                                files=files,
                                use_post=use_post,
                                raw=raw,
                                max_retries=max_retries,
                                timeout=timeout)
        elif data.get('description') == 'Bad Request: message to delete not found':
            return   # The message is already removed
        elif data.get('description') == 'Forbidden: bot was blocked by the user':
            return
    else:
        print(resp.__dict__)
        pass
    return resp


class Bot:

    def __init__(self, token, offset_handler=None):
        self.token = token
        self.offset_handler = offset_handler
        self.first_name = ''
        self.last_name = ''
        self.username = ''

    @property
    def offset(self):
        return 0 if not self.offset_handler else self.offset_handler()

    @property
    def name(self):
        return self.first_name or self.username or self.last_name

    @property
    def base_url(self):
        return 'https://api.telegram.org/bot{}/'.format(self.token)

    def update(self, *, timeout=60):
        url = self.base_url + "getUpdates"
        payload = {'offset': self.offset or "", 'timeout': timeout}
        updates = get_response(url, params=payload)
        # self.offset = updates[-1]['update_id'] + 1
        # if self.offset_handler: self.offset_handler(self.offset)
        return updates

    def update_information(self):
        url = self.base_url + 'getMe'
        resp = get_response(url)
        if resp:
            self.username = resp.get('username')
            self.first_name = resp.get('first_name')
            self.last_name = resp.get('last_name')
        return resp

    def get_group_member(self, participant_group, participant):
        url = self.base_url + 'getChatMember'
        payload = {'chat_id': participant_group, 'user_id': participant}
        return get_response(url, params=payload)

    def send_message(self,
                     group: str or int,
                     text,
                     *,
                     parse_mode='HTML',
                     reply_to_message_id=None,
                     silent=False):
        if not (isinstance(group, str) or isinstance(group, int)):
            group = group.telegram_id

        if parse_mode == 'Markdown':
            text = text.replace('_', '\_')
        blocks = []
        if len(text) > MESSAGE_MAX_LENGTH:
            current = text
            while len(current) > MESSAGE_MAX_LENGTH:
                f = current.rfind('. ', 0, MESSAGE_MAX_LENGTH)
                blocks.append(current[:f + 1])
                current = current[f + 2:]
            blocks.append(current)
        else:
            blocks.append(text)
        resp = []
        for message in blocks:
            url = self.base_url + 'sendMessage'
            payload = {
                'chat_id': group,
                'text': message.replace('<', '&lt;').replace('\\&lt;', '<'),
                'reply_to_message_id': reply_to_message_id if not resp else
                                       resp[-1].get('message_id'),
                'disable_notification': silent,
            }
            if parse_mode:
                payload['parse_mode'] = parse_mode
            resp_c = get_response(url, params=payload)
            resp.append(resp_c)
        return resp

    def send_image(self,
                   participant_group: 'text/id or group',
                   image_file: io.BufferedReader or str,
                   *,
                   caption='',
                   parse_mode='HTML',
                   reply_to_message_id=None,
                   silent=False):
        if parse_mode == 'Markdown':
            caption = caption.replace('_', '\\_')
        if not (isinstance(participant_group, str) or
                isinstance(participant_group, int)):
            participant_group = participant_group.telegram_id
        url = self.base_url + 'sendPhoto'
        payload = {
            'chat_id': participant_group,
            'caption': caption,
            'reply_to_message_id': reply_to_message_id,
            'disable_notification': silent,
        }
        if isinstance(image_file, str):
            payload['photo'] = image_file
            print("The image file is", image_file)
            files = None
        else:
            files = {'photo': image_file}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        resp = get_response(
            url,
            params=payload,
            files=files,
        )
        return resp

    def send_document_by_file_id(self,
                                 group: str,
                                 file_id: str or int,
                                 *,
                                 caption=None,
                                 reply_to_message_id=None,
                                 silent=False):
        file_id = str(file_id)
        url = self.base_url + 'sendDocument'
        payload = {
            'chat_id': group,
            'caption': caption,
            'reply_to_message_id': reply_to_message_id,
            'document': file_id,
            'disable_notification': silent,
        }
        resp = get_response(
            url, params=payload, headers={"Content-Type": "application/json"})
        return resp

    def send_document(self,
                      group: str,
                      file: io.BufferedReader,
                      *,
                      caption=None,
                      reply_to_message_id=None,
                      silent=False):
        if not (isinstance(group, str) or isinstance(group, int)):
            group = group.telegram_id
        url = self.base_url + 'sendDocument'
        payload = {
            'chat_id': group,
            'caption': caption,
            'reply_to_message_id': reply_to_message_id,
            'disable_notification': silent,
        }
        files = {'document': file}
        resp = get_response(
            url,
            params=payload,
            files=files,
        )
        return resp

    def delete_message(self, participant_group: str, message_id: int or str):
        if not (isinstance(participant_group, str) or
                isinstance(participant_group, int)):
            participant_group = participant_group.telegram_id
        url = self.base_url + 'deleteMessage'
        payload = {'chat_id': participant_group, 'message_id': message_id}
        resp = get_response(url, params=payload)
        return resp

    def __str__(self):
        return '[BOT] {}'.format(self.first_name or self.username or
                                 self.last_name)

    class Meta:
        verbose_name = 'Bot'
        db_table = 'db_bot'