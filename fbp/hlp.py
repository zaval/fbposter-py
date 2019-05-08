import os
from urllib.request import urlopen
import re
import sqlite3
from logging.handlers import QueueListener
from kivy.app import App


class FBQueueListener(QueueListener):

    def prepare(self, record):
        with open('log.txt', 'a') as f:
            f.write('{}\n'.format(record.getMessage()))

        app = App.get_running_app()
        # try:
        app.log_text += '{}\n'.format(record.getMessage())
        # except:
        #     pass

        return super(FBQueueListener, self).prepare(record)


def parse_page_info(page_id):
    try:
        page = urlopen('https://www.facebook.com/{}/'.format(page_id)).read().decode()
    except:
        return

    real_id = re.search(r'content="fb://page/(\d+)', page)
    if real_id:
        real_id = real_id.group(1)
    else:
        real_id = page_id

    print(real_id)

    img = re.search(r'meta property="og:image" content="([^"]+)', page)
    try:
        img = img.group(1).replace('&amp;', '&')
        print(img)
        p = urlopen(img).read()
        with open('../asset/{}.png'.format(real_id), 'wb') as f:
            f.write(p)
    except:
        img = None

    conn = sqlite3.connect('{}/../asset/db.sqlite'.format(os.path.dirname(os.path.realpath(__file__))))
    # conn.set_trace_callback(print)
    cursor = conn.cursor()
    if img:
        cursor.execute(
            'update pages set page_id = ?, img = ? where page_id="{}"'
            .format(page_id),
            [real_id, '../asset/{}.png'.format(real_id)]
        )
    else:
        cursor.execute(
            'update pages set page_id = ? where page_id = "{}"'.format(page_id),
            [real_id]
        )
    conn.commit()
    conn.close()


def db_execute(query, *args):
    conn = sqlite3.connect('{}/../asset/db.sqlite'.format(os.path.dirname(os.path.realpath(__file__))))
    cursor = conn.cursor()
    cursor.execute(query, args)
    if query.lower().startswith('select'):
        res = cursor.fetchall()
        return res
    else:
        conn.commit()
        return []
