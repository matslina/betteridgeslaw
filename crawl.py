#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import re
import cPickle
import os
import os.path
import shutil
import time
import os
import sys
import HTMLParser
import httplib
import threading

import BeautifulSoup
import mechanize

ARTICLE_COUNT = 2000
VERBOSE = False
THREADS = 8

sys.setrecursionlimit(10000)


class NewsCrawler(object):
    """Crawls a news site and persists found articles to disk."""

    URL = NotImplementedError()

    # Override this
    def is_article(self, url):
        raise NotImplementedError()

    # And probably also this
    def cleanup_title(self, title):
        raise NotImplementedError()

    def may_crawl(self, url):
        raise NotImplementedError()

    def __init__(self):
        self.state = {'url_visited': set(),
                      'url_new': set([self.URL]),
                      'articles': {},
                      'source': self.name}
        self.fname = "state_%s.pkl" % self.__class__.__name__
        if os.path.exists(self.fname):
            self.state = cPickle.load(open(self.fname))
        self.parser = HTMLParser.HTMLParser()

    def _sync_state(self):
        """Persists state to disk."""

        f = open(self.fname + '.tmp', 'w')
        cPickle.dump(self.state, f)
        f.close()
        os.rename(self.fname + '.tmp', self.fname)

    def _fetch(self, url):
        """Fetches a URL.

        Returns tuple (title, urls) where urls is list of all links
        found at URL.
        Returns None if url was somehow unfetchable.
        """

        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_handle_refresh(False)
        br.addheaders = [('User-agent',
                          ('Mozilla/5.0 (X11; U; Linux i686; en-US; '
                           'rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.'
                           '1-1.fc9 Firefox/3.0.1'))]
        try:
            page = br.open(url).read()
        except (mechanize.HTTPError,
                mechanize.URLError,
                mechanize.BrowserStateError,
                httplib.BadStatusLine):
            return None

        soup = BeautifulSoup.BeautifulSoup(page)
        t = soup.find('title')
        title = t.contents[0] if t and t.contents else 'None'
        urls = []
        for a in soup.findAll('a'):
            if a.has_key('href'):
                if a['href'].startswith("/"):
                    urls.append(self.URL + a['href'][1:])
                else:
                    urls.append(a['href'])
        if not title.strip:
            return None
        return (title.strip(), urls)

    def crawl(self, n):
        """Crawls the site until n articles have been found."""

        url_new = self.state['url_new']
        url_visited = self.state['url_visited']
        articles = self.state['articles']

        if len(articles) >= n:
            return

        print ("Crawling %s, %d new, %d old, %d articles" %
               (self.__class__.__name__,
                len(url_new), len(url_visited), len(articles)))

        while len(articles) < n:

            # without new URLs to fetch, we're dead in the water
            if not url_new:
                print "EEEEEEEK, ran out of URLs!"
                break

            # fetch a random URL
            url = random.choice(tuple(url_new))
            title_links = self._fetch(url)
            if title_links is None or not self.may_crawl(url):
                url_new.remove(url)
                url_visited.add(url)
                continue
            title, links = title_links

            # mark as visited and possibly add to set of articles
            ctitle = self.parser.unescape(self.cleanup_title(title))
            url_new.remove(url)
            url_visited.add(url)
            if self.is_article(url):
                articles.setdefault(ctitle, []).append((title, url))

            if VERBOSE:
                print '-' * 30
                print ctitle
                print title
                print url
                print self.is_article(url)

            # pull out all relevant links at them to the todo
            for l in links:
                if l not in url_visited and self.may_crawl(l):
                    url_new.add(l)

            # periodic state sync
            if len(url_visited) % 100 == 9:
                self._sync_state()

                print ("Crawled %s, %d new, %d old, %d articles" %
                       (self.__class__.__name__,
                        len(url_new),
                        len(url_visited),
                        len(articles)))

        self._sync_state()


class NYTimesCrawler(NewsCrawler):
    URL = "http://www.nytimes.com/"
    url_re = re.compile(r'http://.*nytimes\.com/20[01][0-9]/[0-9]{2}/[0-9]{2}.*')
    name = 'NYTimes'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        i =  title.rfind(u'-')
        if i > 0:
            title = title[:i].strip()
        return title

    def may_crawl(self, url):
        return 'nytimes.com' in url


class BBCCrawler(NewsCrawler):
    URL = "http://www.bbc.com/"
    url_re = re.compile(r'http://www\.bbc\.(com|co\.uk)/news/.*[0-9]+')
    name = 'BBC'

    def is_article(self, url):
        x = bool(self.url_re.match(url))
        return x and not url.endswith('default.stm')

    def cleanup_title(self, title):
        return ''.join(title.split('-')[1:]).strip()

    def may_crawl(self, url):
        return ('bbc' in url and
                'shop.bbc' not in url and
                'stumbleupon' not in url and
                'google.com' not in url and
                'linkedin' not in url and
                'twitter.com' not in url and
                'facebook.com' not in url and
                'digg.com' not in url and
                '/programmes/' not in url and
                'reddit.com' not in url and
                '/cbeebies/' not in url and
                'ssl.bbc' not in url and
                '/comments/' not in url and
                '/sport/' not in url and
                '/music/' not in url and
                'downloads.bbc' not in url)


class HuffPostCrawler(NewsCrawler):
    URL = "http://www.huffingtonpost.com/"
    url_re = re.compile(r'http://.*\.huffingtonpost\.com/20[01][0-9]/[0-9]{2}/[0-9]{2}.*')
    name = 'HuffPost'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return title

    def may_crawl(self, url):
        return 'huffington' in url and 'voces' not in url


class DailyMailCrawler(NewsCrawler):
    URL = "http://www.dailymail.co.uk/"
    url_re = re.compile(r'http://www\.dailymail\.co\.uk/.*article-[0-9]{7}/.*\.html')
    name = 'DailyMail'

    def is_article(self, url):
        x = bool(self.url_re.match(url))
        return x and not url.endswith("emailArticle.html")

    def cleanup_title(self, title):
        return (title + '|').split('|')[0].strip()

    def may_crawl(self, url):
        return 'dailymail' in url


class FoxNewsCrawler(NewsCrawler):
    URL = "http://www.foxnews.com/"
    url_re = re.compile(r'http://.*foxnews\.com/.*/20[01][0-9]/'
                        r'[0-9]{2}/[0-9]{2}/.*')
    name = 'FoxNews'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title + '|').split('|')[0].strip()

    def may_crawl(self, url):
        return 'foxnews' in url and 'video.foxnews' not in url


# This one is a bit iffy still
class CNNCrawler(NewsCrawler):
    URL = "http://www.cnn.com/"
    url_re = re.compile(r'http://.*\.cnn\.com/[a-zA-Z]*/?'
                        r'20[01][0-9]/[0-9]{2}/[0-9]{2}/.+')
    name = 'CNN'

    def is_article(self, url):
        return bool(self.url_re.match(url)) and 'comment' not in url

    def cleanup_title(self, title):
        sep = title.find('&#8211')
        if sep > 0:
            title = title[:sep]
        return (title + ' - ').split(' - ')[0].strip()

    def may_crawl(self, url):
        return ('cnn' in url and 'TRANSCRIPTS' not in url
                and 'ac360' not in url and 'cnnmexico' not in url)


class WashingtonPostCrawler(NewsCrawler):
    URL = "http://www.washingtonpost.com/"
    url_re = re.compile(r'http://.*\.washingtonpost\.com/.*/?'
                        r'20[01][00-9]/[0-9]{2}/[0-9]{2}/.*')
    name = 'WashingtonPost'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title.strip().replace('\n', ' ') + '-').split('-')[0].strip()

    def may_crawl(self, url):
        return 'washingtonpost' in url


class LATimesCrawler(NewsCrawler):
    URL = "http://www.latimes.com/"
    url_re = re.compile(r'http://www\.latimes\.com/.*20[01][0-9]{5}.*story.*')
    name = 'LATimes'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title + ' - ').split(' - ')[0].strip()

    def may_crawl(self, url):
        return 'latimes' in url


class ReutersCrawler(NewsCrawler):
    URL = "http://www.reuters.com/"
    url_re = re.compile(r'http://www.reuters.com/article/'
                        r'20[01][0-9]/[0-9]{2}/[0-9]{2}/.*')
    name = 'Reuters'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title.strip() + '\n').split('\n')[0].strip()

    def may_crawl(self, url):
        return 'reuters' in url and '/video/' not in url


class WallStreetJournalCrawler(NewsCrawler):
    URL = "http://online.wsj.com/"
    url_re = re.compile(r'http://(www|online).wsj.com/(news/)?articles?/.*')
    name = 'WallStreetJournal'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title.strip() + ' - ').split(' - ')[0].strip()

    def may_crawl(self, url):
        return 'wsj.com' in url


class USATodayCrawler(NewsCrawler):
    URL = "http://www.usatoday.com/"
    url_re = re.compile(r'http://www.usatoday.com/(.*/)?story/.*')
    name = 'USAToday'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return title

    def may_crawl(self, url):
        return ('usatoday.com' in url and
                'mediagallery' not in url and
                'sportsdata' not in url and
                'sportspolls' not in url and
                '/tag/' not in url and
                '/salaries/' not in url and
                '/statistics/' not in url and
                '/event/' not in url)


class DailyNewsCrawler(NewsCrawler):
    URL = "http://www.nydailynews.com/"
    url_re = re.compile(r'http://www.nydailynews.com/.*-article-.*')
    name = 'NYDailyNews'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title.strip() + ' - ').split(' - ')[0].strip()

    def may_crawl(self, url):
        return 'nydailynews' in url


class NewYorkPostCrawler(NewsCrawler):
    URL = "http://nypost.com/"
    url_re = re.compile(r'http://nypost.com/20[01][0-9]/[0-9]{2}/[0-9]{2}/.*/$')
    name = 'NewYorkPost'

    def is_article(self, url):
        return bool(self.url_re.match(url))

    def cleanup_title(self, title):
        return (title.strip() + '|').split('|')[0].strip()

    def may_crawl(self, url):
        return 'nypost.com' in url


crawlers = [NYTimesCrawler(),
            BBCCrawler(),
            HuffPostCrawler(),
            DailyMailCrawler(),
            FoxNewsCrawler(),
            CNNCrawler(),
            WashingtonPostCrawler(),
            LATimesCrawler(),
            ReutersCrawler(),
            WallStreetJournalCrawler(),
            USATodayCrawler(),
            DailyNewsCrawler(),
            NewYorkPostCrawler()]


def main():
    active = []
    for c in crawlers:
        # c.crawl(ARTICLE_COUNT)
        # continue
        while len(active) >= THREADS:
            for i in range(len(active)):
                active[i].join(1.0)
                if not active[i].isAlive():
                    active.pop(i)
                    break

        t = threading.Thread(target=c.crawl, args=(ARTICLE_COUNT,),
                             name=c.__class__.__name__)
        t.start()
        active.append(t)

    return 0

if __name__ == "__main__":
    sys.exit(main())
