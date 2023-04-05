#! /usr/bin/env python3

import feedparser
import hashlib
import requests
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import nltk
from heapq import nlargest
import tempfile
import json
from googletrans import Translator
import dbm
import os
import base64

HACKERNEWS_FEED = "https://hnrss.org/newest"

translator = Translator(service_urls=['translate.google.com'])

def hashData(line : str) -> str:
    return hashlib.sha256(line.encode('utf-8')).hexdigest()

def getHtmlContent(link : str) -> str:
    response = requests.get(link)
    html_content = response.text
    return response.text

def getImageExtension(image_line: str) -> str:
    image = os.path.basename(image_line)
    return image.split('.')[-1]

def getImage(link : str) -> str:
    response = requests.get(link)

    image_file = tempfile.mkstemp(prefix=getImageExtension(link))
    with open(image_file[1], "wb") as f:
        f.write(response.content)
    return image_file[1]

def prettyprint(data):
    if type(data) == dict():
        print(json.dumps(data, indent=4))
    elif type(data) == list():
        for e in data:
            prettyprint(e)
    else:
        print(data)

class NewsBot:
    def __init__(self):
        import argparse

        parse = argparse.ArgumentParser(
            description='Automated Bot to Post into Joomla4 sites')
        parse.add_argument('--config', help="configuration file")

        args = parse.parse_args()
        if args.config is None:
            raise Exception('Missing --config')

        self.configFile = args.config

        self.articles = []
        self.readConfiguration()
        self.readDB()

    def readConfiguration(self):
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(self.configFile)
        self.wordpress = {
            'site' : cfg.get('WORDPRESS', 'SITE')
            'username' : cfg.get('WORDPRESS', 'USERNAME'),
            'password' : cfg.get('WORDPRESS', 'PASSWORD'),
        }
        self.dbm = cfg.get('GENERAL', 'DBFILE')

    def readDB(self):
        with dbm.open(self.dbm, 'c') as d:
            try:
                self.published_articles = d['published']
            except KeyError:
                self.published_articles = []

    def writeDB(self):
        with dbm.open(self.dbm, 'c') as d:
            if len(self.published_articles) > 30:
                d['published'] = self.published_articles[-30:]
            else:
                d['published'] = self.published_articles

    def getHackerNews(self) -> list:
        '''
        get the news from rss and return as dict
        '''
        fp = feedparser.parse(HACKERNEWS_FEED)

        for e in fp['entries']:
            hash_id = hashData(e['id'])
            if hash_id in self.published_articles:
                continue
            self.articles.append({
                'title' : e['title'],
                'link' : e['link'],
                'id' : hash_id
            })

    def getArticles(self) -> list:
        '''
        Open each news from the list, fetch the data and try to generate a summary.
        If succeed, then add to the list.
        '''
        articles = list()
        for n in self.articles:
            html_content = getHtmlContent(n['link'])
            soup = BeautifulSoup(html_content, "html.parser")

            article_text = ""
            for element in soup.select("article p"):
                article_text += "\n" + element.text

            try:
                sentences = sent_tokenize(article_text)
            except LookupError:
                print("initializing nltk")
                nltk.download('punkt')
                nltk.download('stopwords')

                # trying again
                sentences = sent_tokenize(article_text)

            stop_words = set(stopwords.words("english"))
            word_frequencies = FreqDist()
            for word in nltk.word_tokenize(article_text):
                if word.lower() not in stop_words:
                    word_frequencies[word.lower()] += 1

            sentence_scores = {}
            for sentence in sentences:
                for word in nltk.word_tokenize(sentence.lower()):
                    if word in word_frequencies.keys():
                        if len(sentence.split(" ")) < 30:
                            if sentence not in sentence_scores.keys():
                                sentence_scores[sentence] = word_frequencies[word]
                            else:
                                sentence_scores[sentence] += word_frequencies[word]

            summary_sentences = nlargest(
                5, sentence_scores, key=sentence_scores.get)
            summary = " ".join(summary_sentences)

            if len(summary) < 5:
                # summary too short, so skip to the next
                continue

            img_tags = soup.find_all('img')
            img_url = None
            if img_tags:
                try:
                    img_url = img_tags[0]['src']
                except KeyError:
                    pass

            if img_url is None:
                # no image found, so skip to the next
                continue

            print('translating:', n['title'])
            translated_summary = translator.translate(summary, src='en', dest='pt')
            if len(translated_summary.text) < 5:
                print(' * failed...')
                continue
            translated_title = translator.translate(
                n['title'], src='en', dest='pt')

 
            articles.append({
                'title': translated_title.text,
                'summary': translated_summary.text,
                'link': n['link'],
                'id': n['id'],
                'image': img_url
            })
        return articles

    def generateAlias(self, line : str) -> str:
        import re

        line = line.lower()
        line = re.sub(" ", "-", line)
        line = re.sub("á|ã|å", "a", line)
        line = re.sub("ó|õ|ö", "o", line)
        line = re.sub("í|ï", "i", line)
        line = re.sub("ç", "c", line)
        return line

    def publishWordPress(self):
        from wordpress_xmlrpc import Client, WordPressPost
        from wordpress_xmlrpc.methods import posts, media
        from wordpress_xmlrpc.compat import xmlrpc_client

        url = self.wordpress['site']
        username = self.wordpress['username']
        password = self.wordpress['password']

        client = Client(url, username, password)

        for art in self.articles:
            # start by image - if fail, just move on to next
            try:
                image_file = getImage(art['image'])
            except requests.exceptions.MissingSchema:
                continue

            image_filename = os.path.basename(art['image'])

            data = {
                #"alias": self.generateAlias(art['title']),
                #"articletext": art['summary'],
                #"catid": 9,  # 9 is blogs for us - we shouldn't hard code here
                #"category" : "Blog",
                #"language": "*",
                #"metadesc": "",
                #"metakey": "",
                #"title": art['title']
                "name": image_filename,
                "type": "image/jpeg",
                "bits": xmlrpc_client.Binary(image_file),
                "overwrite": True
            }
            response = client.call(media.UploadFile(data))
            attachment_id = None
            if response:
                attachment_id = response["id"]

            post = WordPressPost()
            post.title = art['title']
            post.content = art['summary']
            post.post_status = "publish"
            if attachment_id is not None:
                post.thumbnail = attachment_id
            post_id = client.call(posts.NewPost(post))
            print('Posted:', art['title']


    def run(self):
        self.getHackerNews()
        prettyprint(self.articles)

        self.articles = self.getArticles()
        prettyprint(self.articles)

        self.publishWordPress()


if __name__ == '__main__':
    news = NewsBot()
    news.run()
