import os
import sqlite3
from threading import Thread
from queue import Queue
import logging
from logging.handlers import QueueHandler
from fbp.hlp import *
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
try:
    from kivymd.grid import SmartTileWithLabel
except:
    from kivymd.imagelists import SmartTileWithLabel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivymd.theming import ThemeManager
from fbp.fb import FB
from kivy.clock import Clock
from kivy.core.window import Window
from kivymd.dialog import MDDialog
from kivymd.label import MDLabel


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class PagesTile(SmartTileWithLabel):
    page_name = StringProperty('')
    page_id = StringProperty('')
    page_img = StringProperty('')
    page_token = StringProperty('')
    page_times = StringProperty('')
    page_link = StringProperty('')

    def __init__(self, **kwargs):
        super(PagesTile, self).__init__(**kwargs)
        if 'page_name' in kwargs:
            self.page_name = kwargs['page_name']
            self.text = self.page_name
        if 'page_id' in kwargs:
            self.page_id = kwargs['page_id']
        if 'page_img' in kwargs:
            self.page_img = kwargs['page_img']
            self.source = self.page_img
        if 'page_token' in kwargs:
            self.page_token = kwargs['page_token']
        if 'page_times' in kwargs:
            self.page_times = kwargs['page_times']
        if 'page_link' in kwargs:
            self.page_link = kwargs['page_link']

        self.mipmap = True
        self.pos_hint = {'x': .6, 'y': .6}
        self.size_hint = (.6, .6)


class FBPoster(App):
    title = "Facebook Poster"
    theme_cls = ThemeManager()
    pwd = os.path.dirname(os.path.realpath(__file__))
    drafts = []
    posts = []
    videos = []
    total_drafts = 0
    total_videos = 0
    total_posts = 0
    pageTiles = []
    drafts_progress = NumericProperty(0)
    posts_progress = NumericProperty(0)
    video_progress = NumericProperty(0)
    log_text = StringProperty('')

    migrations = [
        '''create table pages (
        name text,
        page_id text,
        link text,
        img text,
        token text,
        times text
        );''',
    ]

    def build(self):

        self.icon = 'asset/icon.png'
        main_widget = Builder.load_file('asset/main.kv')
        pages_grid = main_widget.ids['pages_grid']

        if not os.path.exists('{}/asset/db.sqlite'.format(self.pwd)):
            conn = sqlite3.connect('{}/asset/db.sqlite'.format(self.pwd))
            cursor = conn.cursor()
            for migration in self.migrations:
                cursor.execute(migration)
                conn.commit()
            conn.close()

        self.make_grid(pages_grid)
        Clock.schedule_interval(self.update_progress, .5)

        Window.size = (900, 700)

        return main_widget

    def make_grid(self, pages_grid):
        for c in pages_grid.children[:]:
            pages_grid.remove_widget(c)
        res = db_execute('select * from pages')
        for i, page in enumerate(res):
            pages_grid.add_widget(PagesTile(
                page_name=page[0],
                page_img=page[3],
                page_id=page[1],
                page_token=page[4],
                page_link=page[2],
                size_hint_x=None,
                width=200,
                on_release=lambda x: self.paint_page_tile(x.page_name),
            ))
            ch = len(pages_grid.children)
        pages_grid.cols = 4
        pages_grid.spacing = dp(10)

        # if ch < 4:
        #     pages_grid.spacing = pages_grid.width - 2 * ch

    def update_progress(self, e):
        if len(self.drafts) == 0:
            self.total_drafts = 0
            self.root.ids.start_drafts.text = self.root.ids.start_drafts.text.replace('Стоп', 'Старт')
            self.root.ids.start_schedule.text = self.root.ids.start_schedule.text.replace('Стоп', 'Старт')

        try:
            self.drafts_progress = (100 * (self.total_drafts - len(self.drafts)))/self.total_drafts
        except:
            self.drafts_progress = 0

        if len(self.posts) == 0:
            self.total_posts = 0
            self.root.ids.posts_start.text = 'Конвертировать'

        try:
            self.posts_progress = (100 * (self.total_posts - len(self.posts)))/self.total_posts
        except:
            self.posts_progress = 0

        if len(self.videos) == 0:
            self.total_videos = 0
            self.root.ids.video_start.text = 'Скачать'

        try:
            self.video_progress = (100 * (self.total_videos - len(self.videos)))/self.total_videos
        except:
            self.video_progress = 0

    def paint_page_tile(self, page_name):
        res = db_execute('select * from pages where name = "{}"'.format(page_name))

        self.root.ids.details_page_name.text = res[0][0]
        self.root.ids.details_page_link.text = res[0][2]
        self.root.ids.details_page_id.text = res[0][1]
        self.root.ids.details_page_token.text = res[0][4]
        self.root.ids.details_page_times.text = res[0][5]
        self.root.ids.scr_mngr.current = 'page_details'

    def delete_page(self):
        content = MDLabel(font_style='Body1',
                          theme_text_color='Secondary',
                          text="Удалить страницу {}".format(self.root.ids.details_page_name.text),
                          size_hint_y=None,
                          valign='top')
        content.bind(texture_size=content.setter('size'))
        self.dialog = MDDialog(title="Удаление страницы",
                               content=content,
                               size_hint=(.8, None),
                               height=dp(200),
                               auto_dismiss=False)

        self.dialog.add_action_button("Нет",
                                      action=lambda *x: self.dialog.dismiss())
        self.dialog.add_action_button("Да",
                                      action=lambda *x: self.confirm_delete_dialog(self.root.ids.details_page_id.text)  )
        self.dialog.open()

    def confirm_delete_dialog(self, page_id):
        db_execute('delete from pages where page_id = "{}"'.format(page_id))
        self.dialog.dismiss()
        self.root.ids.pages_grid.clear_widgets()
        # self.build()
        self.make_grid(self.root.ids.pages_grid)
        self.root.ids.scr_mngr.current = 'pages'

    def add_page(self):
        if not self.root.ids.add_page_name.text or not self.root.ids.add_page_link.text or not self.root.ids.add_page_id.text:
            return

        conn = sqlite3.connect('{}/db.sqlite'.format(self.pwd))
        cursor = conn.cursor()

        cursor.execute(
            '''insert into pages values (?, ?, ?, ?, ?, "")''',
            [
                self.root.ids.add_page_name.text.strip(),
                self.root.ids.add_page_id.text.strip(),
                self.root.ids.add_page_link.text.strip(),
                './asset/fb-logo.png',
                self.root.ids.add_page_token.text.strip()
            ]
        )
        conn.commit()
        conn.close()
        self.root.ids.pages_grid.add_widget(
            PagesTile(
                page_name=self.root.ids.add_page_name.text,
                page_img='{}/fb-logo.png'.format(self.pwd),
                on_release = lambda x: self.paint_page_tile(x.page_name),
            )
        )
        ch = len(self.root.ids.pages_grid.children)
        self.root.ids.pages_grid.cols = ch if ch < 4 else 4
        self.root.ids.scr_mngr.current = 'pages'

        Clock.schedule_once(lambda x: self.add_page_parse(self.root.ids.add_page_id.text), 1)

    def add_page_parse(self, page_id):
        parse_page_info(page_id)
        self.make_grid(self.root.ids.pages_grid)

    def load_file(self, path, fname):
        if not fname:
            return
        with open(os.path.join(path, fname[0]), 'rb') as f:
            self.drafts = f.read().decode('utf-8', 'ignore').strip().split('\n')[::-1]
        self.total_drafts = len(self.drafts)
        self.root.ids.details_page_open_file.text = re.sub(
            r'\s*\(\S+\)\s*', '', self.root.ids.details_page_open_file.text)
        self.root.ids.details_page_open_file.text += ' ({})'.format(len(self.drafts))
        self.dismiss_popup()

    def dismiss_popup(self):
        self.root._popup.dismiss()

    def open_file_dialog(self):
        content = LoadDialog(load=self.dismiss_popup, cancel=self.dismiss_popup)
        self.root._popup = Popup(
            title="Открыть файл",
            content=content,
            size_hint=(0.9, 0.9))
        self.root._popup.open()

    def start_drafts(self):

        db_execute('update pages set token = "{}" where page_id = "{}"'.format(self.root.ids.details_page_token.text, self.root.ids.details_page_id.text))
        if 'Стоп' in self.root.ids.start_drafts.text:
            self.drafts = []
            return
        self.root.ids.start_drafts.text = self.root.ids.start_drafts.text.replace('Старт', 'Стоп')
        fb = FB(self.root.ids.details_page_token.text, self.root.ids.details_page_id.text)
        fb.start_drafts(self.drafts)

    def set_drafts_len(self, x):
        print(x)
        self.total_drafts = x

    def start_schedule(self):
        db_execute('update pages set token = "{}", times = "{}" where page_id = "{}"'.format(self.root.ids.details_page_token.text, self.root.ids.details_page_times.text, self.root.ids.details_page_id.text))
        if len(self.drafts) > 0:
            return
        fb = FB(self.root.ids.details_page_token.text, self.root.ids.details_page_id.text, self.root.ids.details_page_link.text)
        self.drafts = fb.jobs
        fb.times = re.findall(r'(\d+:\d+)', self.root.ids.details_page_times.text)
        if not fb.times:
            return
        fb.start_schedule(self.set_drafts_len)

    def download_video(self):
        if 'Стоп' in self.root.ids.video_start.text:
            self.videos = []
            return
        self.root.ids.video_start.text = 'Стоп'
        self.videos = self.root.ids.video_links.text.replace('\r', '').split('\n')[::-1]
        self.total_videos = len(self.videos)
        t = Thread(target=FB.download_videos, args=(self.videos,), daemon=True)
        t.start()

    def download_posts(self):
        if 'Стоп' in self.root.ids.posts_start.text:
            self.posts = []
            return
        self.root.ids.posts_start.text = 'Стоп'
        self.posts = self.root.ids.post_links.text.replace('\r', '').split('\n')[::-1]
        self.total_posts = len(self.posts)
        t = Thread(target=FB.download_posts, args=(self.posts,), daemon=True)
        t.start()

if __name__ == '__main__':
    que = Queue(-1)
    # print(logging.root.manager.loggerDict)
    queue_handler = QueueHandler(que)
    handler = logging.StreamHandler()
    listener = FBQueueListener(que, handler)
    root = logging.getLogger('FB')
    root.addHandler(queue_handler)
    formatter = logging.Formatter('%(threadName)s: %(message)s')
    handler.setFormatter(formatter)
    listener.start()

    FBPoster().run()
    listener.stop()
