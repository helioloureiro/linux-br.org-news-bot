#! /usr/bin/env python3

import tempfile
import json
import os
import re
import logging
import time
import mimetypes
import sys
import configparser
from heapq import nlargest
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import nltk
from googletrans import Translator
import requests
import feedparser
from bs4 import BeautifulSoup

sys.dont_write_bytecode = True

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


def get_interested_terms():
    'to populated to interested terms'
    global INTERESTED_TERMS
    with open(INTERESTED_TERMS_FILE, encoding="utf-8") as src:
        for line in src.readlines():
            INTERESTED_TERMS.append(line.rstrip())

def getHtmlContent(link : str) -> str: # pylint: disable=C0103
    'To fetch html content and return the text'
    response = requests.get(link, timeout=10)
    return response.text

def getImageExtension(image_line: str) -> str: # pylint: disable=C0103
    'To figure out the image extension name'
    imgType =  mimetypes.guess_type(image_line)[0] # pylint: disable=C0103
    if imgType == "svg+xml":
        imgType = "svg" # pylint: disable=C0103
    return imgType

def getImage(link : str): # pylint: disable=C0103
    'To fetch an image from some url'
    logger.debug('getimage() link: %s', link)
    extension = getImageExtension(link)
    if extension is None:
        logger.debug('getImage(): %s is None', link)
        return None
    response = requests.get(link, timeout=10)

    save_extension = extension.split("/")[1]
    logger.debug('getimage() suffix: %s', save_extension)

    image_file = tempfile.mkstemp(suffix='.' + save_extension)
    with open(image_file[1], "wb") as f:
        f.write(response.content)
    return image_file[1]

def prettyprint(data):
    'Just nice json formmating and printing'
    if isinstance(data, dict):
        print(json.dumps(data, indent=4))
    elif isinstance(data, list):
        for e in data:
            prettyprint(e)
    else:
        print(data)

def applyTextCorrections(text): # pylint: disable=C0103
    'To remove over translations'
    for term, replacement in CORRECTIONS.items():
        if re.search(term, text):
            text = re.sub(term, replacement, text)
    return text

class NewsBot:
    'Class to control bot behavior'
    def __init__(self, config=None):
        if config is None:
            raise Exception('Missing --config') # pylint: disable=W0719

        self.configFile = config # pylint: disable=C0103

        self.articles = []
        self.readConfiguration()

    def readConfiguration(self): # pylint: disable=C0103
        'to read configuration in configparser format'
        cfg = configparser.ConfigParser()
        cfg.read(self.configFile)
        self.wordpress = {
            'site' : cfg.get('WORDPRESS', 'SITE'),
            'token' : cfg.get('WORDPRESS', 'TOKEN')
        }

    def getSiteRSSTitles(self) -> list: # pylint: disable=C0103
        'Fetch the RSS from the site hackernews'
        fp = feedparser.parse(self.wordpress['site'] + '/feed/')
        titles = list()
        for e in fp['entries']:
            titles.append(e['title'])
        return titles

    def isTopicOfInterest(self, text : str) -> bool: # pylint: disable=C0103
        'Check whether a text is in the interesting word list or not'
        score = 0
        words_of_interest = []
        for word in INTERESTED_TERMS:
            # [ \.,]open source[ \.,]|$
            if re.search("[ \.,]" + word.lower() + "[ \.,]", text.lower()):
                score += 1
                words_of_interest.append(word)
            elif re.search("[ \.,]" + word.lower() + "$", text.lower()):
                score += 1
                words_of_interest.append(word)
            elif re.search("^" + word.lower() + "[ \.,]", text.lower()):
                score += 1
                words_of_interest.append(word)
        logger.debug('"%s" [SCORE: %s]', text, score)

        if score == 0:
            return False
        all_words = ', '.join(words_of_interest)
        logger.info("Ranking: [%s] %s", all_words, score)
        return True

    def generateAlias(self, line : str) -> str: #pylint: disable=C0103
        '''
        It removes characters with accent in order to create a nice
        site alias on WordPress in lower case.
        '''
        new_line = line.lower()
        new_line = re.sub(" ", "-", new_line)
        new_line = re.sub("á|ã|å", "a", new_line)
        new_line = re.sub("ó|õ|ö", "o", new_line)
        new_line = re.sub("í|ï", "i", new_line)
        new_line = re.sub("ç", "c", new_line)
        return new_line

    def publishPicture(self, image_link, url, token): #pylint: disable=C0103
        '''
        Publish the picture into WordPress site.
        '''
        image_type = getImageExtension(image_link)
        if image_type is None:
            logger.debug("publishPicture() got image_type as none for: %s", image_link)
            return None
        logger.debug('image: %s', image_link)
        image_path = getImage(image_link)
        logger.debug('image_path: %s', image_path)
        with open(image_path, "rb") as img:
            image_data = img.read()
        image_filename = os.path.basename(image_path)

        logger.debug('image_filename: %s', image_filename)
        logger.debug('image_type: %s', image_type)

        media_headers = {
            "Authorization": "Bearer " + token,
            "Content-Disposition": f"attachment; filename={image_filename}",
            "Cache-control" : "no-cache",
            "Content-type" : image_type
            }

        media_response = requests.post(
            url + "/wp-json/wp/v2/media",
            headers=media_headers,
            data=image_data,
            timeout=30
        )
        # too much data
        #logger.debug('media_response: ' + media_response.text)
        media_id = None
        if media_response.status_code in (200, 201):
            media_id = media_response.json()["id"]
        else:
            logger.warning("Failed to post picture: " +  #pylint: disable=W1201
                           "%s, path: %s, status_code: %d",
                image_link, image_path, media_response.status_code
            )
        logger.debug('removing image: %s', image_path)
        os.unlink(image_path)
        return media_id

    def run(self):
        '''
        Simple bot starting point.
        '''
        self.getHackerNews()
        #prettyprint(self.articles)

        self.articles = self.getArticles()
        #prettyprint(self.articles)

        self.publishWordPress()

    def getHackerNews(self) -> list: # pylint: disable=C0103
        '''
        get the news from rss and return as dict
        '''
        fp = feedparser.parse(HACKERNEWS_FEED)

        for e in fp['entries']:
            self.articles.append({
                'title' : e['title'],
                'link' : e['link'],
            })

    def getArticles(self) -> list: # pylint: disable=C0103
        '''
        Open each news from the list, fetch the data and try to generate a summary.
        If succeed, then add to the list.
        '''
        articles = list()
        for article in self.articles:
            title = article['title']
            if not self.isTopicOfInterest(title):
                logger.info('Not related to something we might like, so we skip: %s', title)
                continue
            logger.info('Interested article: %s', title)

            link = article['link']
            article_text, image_tags = self.get_article_content_and_image(link)
            summary = self.generate_summary(article_text)

            if self.is_summary_too_short(summary):
            # if len(summary) < 5:
                logger.info("Too short summary for: %s (DISCARDED)", title)
                # summary too short, so skip to the next
                continue

            image_url = self.get_image_url_from_tag(title, image_tags)

            if image_url is None:
                logger.warning("Discarding [%s] because of the missed image", title)
                continue

            logger.info('translating: %s', title)
            translated_summary = self.translate_article(summary)

            if translated_summary is None or len(translated_summary) < 5:
                logger.error('failed to translate [%s]', title)
                continue

            translated_title = self.translate_article(title)

            content = self.generate_content_source(translated_summary, link)
            articles.append({
                'title': applyTextCorrections(translated_title),
                'content': content,
                'link': link,
                'image': image_url
            })
        return articles

    def get_article_content_and_image(self, url : str) -> str:
        'Fetch the text from url and return it after parsing'
        try:
            html_content = getHtmlContent(url)
        except ConnectionError:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")

        article_text = ""
        for element in soup.select("article p"):
            article_text += "\n" + element.text

        img_tags = soup.find_all('img')
        return (article_text, img_tags)


    def translate_article(self, text: str) -> str:
        '''
        To translate the texts from English to Portuguese
        '''
        try:
            translated_content = translator.translate(text, src='en', dest='pt')
        except TypeError:
            logger.error("Translation failed for: %s", text)
            return None
        if translated_content.text == text:
            logger.error("Translation failed: %s", translated_content.text)
            return None
        return translated_content.text

    def generate_summary(self, article_text : str) -> str:
        '''
        Get the article and generate an automated summary.
        '''
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
                        if sentence not in sentence_scores:
                            sentence_scores[sentence] = word_frequencies[word]
                        else:
                            sentence_scores[sentence] += word_frequencies[word]

        summary_sentences = nlargest(
            5, sentence_scores, key=sentence_scores.get)
        return " ".join(summary_sentences)

    def is_summary_too_short(self, summary: str) -> bool:
        'Is it shorter than 5 characters?'
        return len(summary) < 5

    def get_image_url_from_tag(self, title: str, image_tags_from_soap: list):
        'Try to find a main image url'
        if image_tags_from_soap is None:
            logger.error("The [%s] has no image tags", title)
            return None

        tags_size = len(image_tags_from_soap)
        if tags_size == 0:
            logger.error("The [%s] has no image tags", title)
            return None
        try:
            img_url = image_tags_from_soap[0]['src']
            return img_url
        except (KeyError, IndexError):
            logger.error("Failed to find image for: [%s] - tags found: %d", title, tags_size)
            return None

    def generate_content_source(self, summary: str, link: str) -> str :
        '''to generate the content to be posted with source information'''
        return applyTextCorrections(summary) + \
            "\n\nFonte: <a href=\"" + link + \
            "\">" + link + "</a>"

    def publishWordPress(self): #pylint: disable=C0103
        '''
        Publish articles into WordPress website.
        '''

        # reference: https://github.com/crifan/crifanLibPython/blob/master/python3/crifanLib/thirdParty/crifanWordpress.py #pylint: disable=C0301

        url = self.wordpress['site']
        token = self.wordpress['token']

        cur_headers = self.generate_http_headers(token)

        published_titles = self.getSiteRSSTitles()

        for art in self.articles:
            if art['image'] is None:
                logger.info("article [%s] missing image", art['title'])
                continue

            if self.is_article_already_published(art, published_titles):
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

            image_type = getImageExtension(art['image'])
            if image_type is None:
                logger.info("Failed to detect image extension [%s] (not published for this reason)", art['title'])
                continue

            media_id = self.publishPicture(art['image'], url, token)
            if  media_id is None:
                logger.info("Failed to fetch image for [%s] (not published for this reason)", art['title'])
                continue
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

    def generate_http_headers(self, token: str) -> str:
        'self explained method'
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def is_article_already_published(self, article_dict: dict, published_titles: list) -> bool:
        'self explained method'
        title = article_dict['title']
        if title in published_titles:
            logger.info('Article [%s] already published', title)
            return True
        return False


if __name__ == '__main__':
    import argparse

    parse = argparse.ArgumentParser(
        description='Automated Bot to Post into WordPress sites')
    parse.add_argument('--config', required=True, help="configuration file")
    parse.add_argument('--loglevel', help="logging level", default="DEBUG")

    args = parse.parse_args()
    if args.config is None:
        raise Exception('Missing --config')

    if args.loglevel is not None:
        logger.setLevel(args.loglevel.upper())

    get_interested_terms()

    logger.info('Starting at: %s', time.ctime())
    news = NewsBot(config=args.config)
    news.run()
