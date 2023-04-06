#! /usr/bin/env python3
# 
# it uses configuration from toot
import os
import json
import argparse
import sys
from mastodon import Mastodon
import requests
import feedparser
import re
import sqlite3

HOME = os.getenv('HOME')
CONFIG = f"{HOME}/.config/toot/config.json"

RSS_SITE = "https://linux-br.org/feed/"
DBM = "f{HOME}/.config/linux-br.org-autonews-bot/mastodon-posts.db"

# mastodon limits toots to 550 characters
POST_LIMIT_SIZE = 550

def sleepMinutes(minutes):
    import time
    print(f'Sleeping {minutes} minutes')
    time.sleep(minutes * 60)

def randomMinutes(maximum : int) -> int:
    import random
    return random.randint(0, maximum)

class TootPostLink:
    def __init__(self, userid, database):
        with open(CONFIG) as tootConfig:
            config = json.load(tootConfig)

        self.mastodon = Mastodon(
            access_token = config['users'][userid]['access_token'], 
            api_base_url = config['users'][userid]['instance']
            )
        self.me = self.mastodon.me()
        print('Mastodon login completed')

        self.database = database

        self.getDataDB()

    def getArticles(self):
        # read articles from rss link
        articles = feedparser.parse(RSS_SITE)
        self.articles = []
        print('selecting articles...')
        for rss in articles.entries:
            #rss = articles.entries[index]
            if rss.title in self.posted_articles:
                # skip and move to the next
                continue
            print('title:', rss.title)
            print(' * link:', rss.link)
            self.articles.append([rss.title, rss.link])
        print('done!')

    def postMastodon(self):
        print('Posting articles')

        while self.articles:
            title, link = self.articles.pop()
            sleepMinutes(randomMinutes(3))
            print(f'Posting: {title}')
            self.mastodon.toot(f"{title}\n\n {link}")
            self.posted_articles.append(link)

    def saveDataDB(self):
        print('Saving data')
        with sqlite3.connect(self.database) as con:
            cur = con.cursor()
            for link in self.posted_articles:
                cur.execute(f"INSERT into posted_articles values (\"{link}\") ")
            con.commit()

    def getDataDB(self):
        print('Getting data from DB')
        self.posted_articles = []
        with sqlite3.connect(self.database) as con:
            cur = con.cursor()
            for item in cur.execute("SELECT * from posted_articles").fetchall():
                self.posted_articles.append(item[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Runs through your following list and recommend them')
    parser.add_argument("--userid", help="Your registered mastodon account at toot configuration")
    parser.add_argument("--sqlite3", help="sqlite3 DB to store information")
    args = parser.parse_args()

    if args.userid is None:
        parser.print_usage()
        sys.exit(os.EX_NOINPUT)

    if not os.path.exists(CONFIG):
        print("ERROR: toot not configured yet.  Use toot to create your configuration.")
        sys.exit(os.EX_CONFIG)

    if args.sqlite3 is None or not os.path.exists(args.sqlite3):
        print("ERROR: missing sqlite3 database")
        sys.exit(os.EX_CONFIG)

    toot = TootPostLink(args.userid, args.sqlite3)
    toot.getArticles()
    toot.postMastodon()
    toot.saveDataDB()

