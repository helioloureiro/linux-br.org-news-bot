#! /usr/bin/env python3

import tempfile
import json
import os
import re
import logging
import time
import mimetypes
from heapq import nlargest
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import nltk
from googletrans import Translator
import requests
import feedparser
from bs4 import BeautifulSoup

HACKERNEWS_FEED = "https://hnrss.org/newest"

translator = Translator(service_urls=['translate.google.com'])

program_path = os.path.dirname(__file__)

INTERESTED_TERMS = [ ]
INTERESTED_TERMS_FILE = f"{program_path}/interests.list"

CORRECTIONS = { 
    "ferrugem" : "rust",
    "concha" : "shell"
}

logging.basicConfig()
logging.root.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

scriptName = os.path.basename(__file__)

logger = logging.getLogger(scriptName)
logger.setLevel('DEBUG')

with open(INTERESTED_TERMS_FILE) as src:
    for line in src.readlines():
        INTERESTED_TERMS.append(line.rstrip())

def getHtmlContent(link : str) -> str:
    response = requests.get(link)
    html_content = response.text
    return response.text

def getImageExtension(image_line: str) -> str:
    return mimetypes.guess_type(image_line)[0]

def getImage(link : str):
    logger.debug('getimage() link: ' + link)
    extension = getImageExtension(link)
    if extension is None:
        logger.debug('getImage(): %s is None', link)
        return None
    response = requests.get(link)

    save_extension = extension.split("/")[1]
    logger.debug('getimage() suffix: %s', save_extension)

    image_file = tempfile.mkstemp(suffix='.' + save_extension)
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

def applyTextCorrections(text):
    for term, replacement in CORRECTIONS.items():
        if re.search(term, text):
            text = re.sub(term, replacement, tex)
    return text

class NewsBot:
    def __init__(self):
        import argparse

        parse = argparse.ArgumentParser(
            description='Automated Bot to Post into WordPress sites')
        parse.add_argument('--config', help="configuration file")
        parse.add_argument('--loglevel', help="logging level", default="DEBUG")

        args = parse.parse_args()
        if args.config is None:
            raise Exception('Missing --config')

        if args.loglevel is not None:
            logger.setLevel(args.loglevel.upper())

        self.configFile = args.config

        self.articles = []
        self.readConfiguration()

    def readConfiguration(self):
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(self.configFile)
        self.wordpress = {
            'site' : cfg.get('WORDPRESS', 'SITE'),
            'token' : cfg.get('WORDPRESS', 'TOKEN')
        }

    def getHackerNews(self) -> list:
        '''
        get the news from rss and return as dict
        '''
        fp = feedparser.parse(HACKERNEWS_FEED)

        for e in fp['entries']:
            self.articles.append({
                'title' : e['title'],
                'link' : e['link'],
            })

    def getSiteRSSTitles(self) -> list:
        fp = feedparser.parse(self.wordpress['site'] + '/feed/')
        titles = list()
        for e in fp['entries']:
            titles.append(e['title'])
        return titles

    def isTopicOfInterest(self, text : str) -> bool:
        score = 0
        for word in INTERESTED_TERMS:
            if re.search(word.lower(), text.lower()):
                score += 1
        logger.debug(f'"{text}" [SCORE: {score}]')
        if score == 0:
            return False
        return True

    def getArticles(self) -> list:
        '''
        Open each news from the list, fetch the data and try to generate a summary.
        If succeed, then add to the list.
        '''
        articles = list()
        for n in self.articles:
            if not self.isTopicOfInterest(n['title']):
                logger.info('Not related to something we might like, so we skip: %s', n['title'])
                continue
            logger.info('Interested article: %s', n['title'])
            try:
                html_content = getHtmlContent(n['link'])
            except:
                continue
            soup = BeautifulSoup(html_content, "html.parser")

            article_text = ""
            for element in soup.select("article p"):
                article_text += "\n" + element.text

            try:
                sentences = sent_tokenize(article_text)
            except LookupError:
                logger.info("initializing nltk")
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
                logger.debug(f"Too short summary for: {summary}")
                # summary too short, so skip to the next
                continue

            img_tags = soup.find_all('img')
            img_url = None
            
            try:
                img_url = img_tags[0]['src']
            except KeyError:
                tags_size = 0
                if img_tags is not None:
                    tags_size = len(img_tags)
                logger.debug(f"Failed to find image for: {summary} - tags found: {tags_size}")
                pass

            logger.info('translating: ' + n['title'])
            try:
                translated_summary = translator.translate(summary, src='en', dest='pt')
            except TypeError:
                # failed to translate, try the next one
                continue
            if len(translated_summary.text) < 5:
                logger.info(' * failed...')
                continue
            translated_title = translator.translate(
                n['title'], src='en', dest='pt')

            content = applyTextCorrections(translated_summary.text)
            content += "\n\nFonte: <a href=\"" + n['link']
            content += "\">" + n['link'] + "</a>"
 
            articles.append({
                'title': applyTextCorrections(translated_title.text),
                'content': content,
                'link': n['link'],
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
    
    def publishPicture(self, image_link, url, token):
        image_type = getImageExtension(image_link)
        if image_type is None:
            logger.debug(f"publishPicture() got image_type as none for: {image_link}")
            return None
        logger.debug('image: ' + image_link)
        image_path = getImage(image_link)
        logger.debug('image_path: ' + image_path)
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_filename = os.path.basename(image_path)

        logger.debug('image_filename: ' + image_filename)
        logger.debug('image_type: ' + image_type)

        media_headers = {
            "Authorization": "Bearer " + token,
            "Content-Disposition": "attachment; filename={}".format(image_filename),
            "Cache-control" : "no-cache",
            "Content-type" : image_type
            }

        media_response = requests.post(url + "/wp-json/wp/v2/media", headers=media_headers, data=image_data)
        # too much data
        #logger.debug('media_response: ' + media_response.text)
        media_id = None
        if media_response.status_code == 200 or media_response.status_code == 201:
            media_id = media_response.json()["id"]
        else:
            logger.warn(f"Failed to post picture: {image_link}, path: {image_path}, status_code: {media_response.status_code}")
        logger.debug('removing image: ' + image_path)
        os.unlink(image_path)
        return media_id



    def publishWordPress(self):
        '''
        Publish articles into WordPress website.
        '''

        # reference: https://github.com/crifan/crifanLibPython/blob/master/python3/crifanLib/thirdParty/crifanWordpress.py

        url = self.wordpress['site']
        token = self.wordpress['token']

        cur_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        published_titles = self.getSiteRSSTitles()

        for art in self.articles:

            if art['title'] in published_titles:
                # skip if already there
                logger.info('Article "%s" already published', art['title'])
                continue
            data = {
                "title": art['title'],
                "content": art['content'],
                "date": None, # '2020-08-17T10:16:34'
                "slug": self.generateAlias(art['title']),
                "status": "publish",
                "format": 'standard',
                "categories": [91], # 91 : notícias
                "tags": [],
            }

            if art['image'] is not None:
                image_type = getImageExtension(art['image'])
                if image_type is not None:
                    media_id = self.publishPicture(art['image'], url, token)
                    if  media_id is not None:
                        data["featured_media"] = media_id

            resp = requests.post(
                f"{url}/wp-json/wp/v2/posts",
                headers=cur_headers,
                # data=json.dumps(postDict),
                json=data, # internal auto do json.dumps
                timeout=30,
            )
            if resp.status_code in (200, 201):
                logger.info('Posted: %s', art['title'])
            else:
                logger.error('FAILED: %s', art['title'])
            logger.debug(' * status code: %s', str(resp.status_code))
            #print(' * resp text:', resp.text)


    def run(self):
        '''
        Simple bot starting point.
        '''
        self.getHackerNews()
        #prettyprint(self.articles)

        self.articles = self.getArticles()
        #prettyprint(self.articles)

        self.publishWordPress()


if __name__ == '__main__':
    logger.info('Starting at: %s', time.ctime())
    news = NewsBot()
    news.run()
