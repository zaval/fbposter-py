import time
import random
import re
import os
from urllib.parse import unquote
from threading import Thread
import requests
import datetime
import logging
from bs4 import BeautifulSoup


log = logging.getLogger('FB')
logging.basicConfig(level=logging.DEBUG)
log.setLevel(logging.DEBUG)


class FB:

    # log = None
    access_token = ''
    group_id = ''
    site_domain = ''
    url_schedule_data = {
        'access_token': access_token,
        '_reqName': 'object:page/scheduled_posts_internal',
        '_reqSrc': 'PageContentTabScheduledPostsConfig',
        'fields': '["admin_creator{name}","scheduled_publish_time"]',
        'filtering': '[]',
        'locale': 'ru_RU',
        'method': 'get',
        'pretty': '0',
        'sort': '["scheduled_publish_time_ascending"]',
        'summary': 'true',
        'suppress_http_code': '1',
        'limit': '1000',
    }

    draft_data = {
        'access_token': access_token,
        '_reqName': 'object:page/draft_posts',
        '_reqSrc': 'PageContentTabDraftsConfig',
        'fields': '["message","modified_time","creation_time","admin_creator{name}","story_token","permalink_url","place{name}","edit_actions{edit_time,editor}","thumbnail","og_action_summary"]',
        'filtering': '[]',
        'force_framework': 'ent',
        'locale': 'ru_RU',
        'method': 'get',
        'pretty': '0',
        'sort': '["edited_by_descending"]',
        'summary': 'true',
        'suppress_http_code': '1',
        'limit': 1000,
    }

    def __init__(self, token, group_id, site_domain=None):

        self.access_token = token
        log.debug('hello')
        self.group_id = group_id
        self.url = 'https://graph.facebook.com/v2.5/{}/draft_posts'.format(group_id)
        self.url_scheduled = 'https://graph.facebook.com/v2.5/{}/scheduled_posts_internal'.format(group_id)
        if site_domain:
            self.site_domain = site_domain

        self.draft_data['access_token'] = self.access_token
        self.url_schedule_data['access_token'] = self.access_token

        self.scheduled = []
        self.jobs = []
        while True:
            data = requests.post(self.url_scheduled.format(self.access_token), data=self.url_schedule_data).json()
            # log.info(data)
            if 'data' not in data or not data['data']:
                break

            self.scheduled += data['data']
            next = data.get('paging', {}).get('next', '')
            if not next:
                break
            log.info(next)
            data = requests.post(next, data=self.url_schedule_data).json()

        self.drafts = []
        if site_domain:
            while True:
                data = requests.post(self.url, data=self.draft_data).json()
                if 'data' not in data or not data['data']:
                    break

                self.drafts += data['data']
                next = data.get('paging', {}).get('next', '')
                if not next:
                    break
                log.info(next)
                data = requests.post(next, data=self.url_schedule_data).json()

    def __post_drafts(self, posts):
        # for post in posts:
        while True:
            try:
                post = posts.pop()
            except:
                break

            post = post.strip()
            if not post:
                continue
            try:
                message, link = post.split('\t')
            except:
                continue
            log.info(link)
            try:
                p = requests.get(link)
                if p.status_code != 200:
                    log.info('{} is 404'.format(link))
                    continue
            except Exception as e:
                continue

            data = {
                'link': link,
                'message': message,
                'published': False,
                'unpublished_content_type': 'DRAFT',
                'access_token': self.access_token,
                # 'feed_targeting': '{"age_max":65,"age_min":18,"geo_locations":{"countries":["AT","BE","BG","AU","DE","CZ","DK","CA","BY","CH","IL","GB","EE","HU","FR","ES","IT","FI","GE","IE","KZ","NO","PT","RU","LV","LT","PL","NL","SK","SE","UA","US"]}}'
            }

            url = 'https://graph.facebook.com/v2.5/{}/feed'.format(self.group_id)

            p = requests.post(url, data=data).text

            log.info(p)

            time.sleep(random.randint(30, 60))

    def start_drafts(self, posts):
        log.info('{} {}'.format(self.access_token, self.group_id, posts))
        t = Thread(target=self.__post_drafts, args=(posts,))
        t.start()

    def date_generator(self):
        diff = datetime.datetime.now() - datetime.datetime.utcnow()
        d = datetime.datetime.now()
        while True:
            for i in self.times:
                h, m = i.split(":")
                h = int(h)
                m = int(m)
                d = d.replace(hour=h, minute=m, second=0)
                if d < datetime.datetime.now():
                    continue
                d1 = d - diff
                yield d1.isoformat().split('.')[0] + '+0000'
            log.info(d)
            d += datetime.timedelta(days=1)

    def start_schedule(self, jobs_cb=None):
        t = Thread(target=self.__post_schedule, args=(jobs_cb,))
        t.start()

    def __post_schedule(self, jobs_cb):

        # log.info(self.drafts)

        # try:
        #     drafts = [x['id'] for x in self.drafts if x['admin_creator']['id'] == self.user_id]
        # except:
        drafts = [x['id'] for x in self.drafts if self.site_domain in x['thumbnail']]
        log.info('total {} drafts'.format(len(drafts)))
        scheduled_times = [x['scheduled_publish_time'] for x in self.scheduled]
        scheduled_times.sort()
        tg = self.date_generator()

        job_data = {}

        for draft in drafts:
            while True:
                t = next(tg)
                if t not in scheduled_times:
                    job_data[draft] = t
                    break

        log.info(job_data)
        # return

        # self.jobs = [x for x in list(job_data.keys())]
        for i in list(job_data.keys()):
            self.jobs.append(i)
        if jobs_cb:
            jobs_cb(len(self.jobs))

        for id_, tm in job_data.items():
            self.jobs.pop()
            ts = int(datetime.datetime.strptime(tm, "%Y-%m-%dT%H:%M:%S%z").timestamp())

            post_url = 'https://graph.facebook.com/v2.5/{}_{}?access_token={}'.format(self.group_id, id_, self.access_token)
            data = {
                '_reqName': 'object:post',
                '_reqSrc': 'PageContentTabActions',
                'locale': 'ru_RU',
                'method': 'post',
                'pretty': '0',
                'scheduled_publish_time': ts,
                'suppress_http_code': '1',
            }

            log.info('posting https://facebook.com/{}/posts/{} to time {}'.format(self.group_id, id_, tm))
            resp = requests.post(post_url, data=data).json()

            log.info(resp)
            if resp.get('success', False) is not True:
                return

            time.sleep(random.randint(5, 15))

    def download_videos(urls):
        http = requests.Session()
        http.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0'})

        if not os.path.exists('video'):
            os.makedirs('video')

        # for i, url in enumerate(urls):
        i = 0
        while True:
            try:
                url = urls.pop()
            except:
                break

            url = url.strip()
            if not url:
                continue

            log.error(url)
            try:
                p = http.get(url.replace('www', 'm')).text
            except Exception as e:
                log.error(e)
                continue

            b = re.search(r'href="/video_redirect/\?src=([^"]+)', p)
            t = re.search(r'data\-ft="&#123;&quot;tn&quot;:&quot;\*s&quot;&#125;"><p>([^<]+)', p)
            if not b:
                continue
            b = b.group(1)

            if not t:
                t  = '😀'
            else:
                t = t.group(1)

            video_url = unquote(b)

            fname = 'video/{}.mp4'.format(i)
            r = http.get(video_url, stream=True)
            with open(fname, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            with open('video/{}.txt'.format(i), 'wb') as f:
                f.write(t.encode())

    def download_posts(links):

        res = []
        while True:
            try:
                post = links.pop()
            except:
                break

            post = post.strip()
            if not post:
                continue

            try:
                p = requests.get(post, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'}).text
                # p = requests.get(post, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.81 Safari/537.36', 'cookie': 'fr=5ej4kKAyecNzK2Ol5.AWVcOo94s59uewcq_h0FfcbJ4Mg.Bb-Dnp.MX.Fx1.0.0.BcdV5z.AWX7hXbZ; sb=6Tn4WyvFzJAMp6KFxVl3kaKa; datr=6Tn4W5voL0dMfy8XyIVdCix-; c_user=100030456708009; xs=12%3AgWIYdBaxqg98qw%3A2%3A1542996075%3A1119%3A15687; wd=1920x908; spin=r.4797121_b.trunk_t.1551188515_s.1_v.2_'}).text
            except:
                log.info('{} ERROR'.format(post))
                res.append('{}\t\t'.format(post))
                continue

            soup = BeautifulSoup(p, 'lxml')

            try:
                cd = soup.find('code').string
            except Exception as e:
                log.info('{} {}'.format(e, post))
                continue

            if not cd:
                log.info('cd not found {}'.format(post))
                continue

            cd = cd.replace('<!--', '').replace('-->', '')

            soup2 = BeautifulSoup(cd, 'lxml')

            try:
                message = soup2.select('div[data-ad-preview="message"] p')[0].prettify()
            except:
                message = ''
                try:
                    message = soup2.select('div.userContent p')[0].prettify()
                except:
                    message = ''
                if not message:
                    try:
                        message = soup2.select('div.mtm p')[0].prettify()
                    except:
                        message = ''

            message = re.sub(r'<.+?>', '', message)
            message = re.sub(r'\s+', ' ', message).strip()

            try:
                link = soup2.select('a[data-lynx-mode="async"]')[0]['href']
                link = link.split('u=')[1].split('&')[0]
                link = unquote(link)
                link = link.split('?')[0]
            except Exception as e:
                log.info(e)
                link = ''

            log.info('{}\t{}\t{}'.format(post, message, link))

            res.append('{}\t{}'.format(message, link))

        with open('posts.csv', 'wb') as f:
            f.write('\n'.join(res).encode('utf-8', 'ignore'))
