#! /usr/bin/env python3

import feedparser
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
import os
import base64
import re
import time

HACKERNEWS_FEED = "https://hnrss.org/newest"

translator = Translator(service_urls=['translate.google.com'])

INTERESTED_TERMS = [ 
    "MySQL",
    "Oracle",
    "Database",
    "PostgreSQL",
    "Linux",
    "MacOS",
    "FreeBSD",
    "OpenBSD",
    "NetBSD",
    "Debian",
    "Archlinux",
    "Fedora",
    "ChatGPT",
    "sendmail",
    "postfix",
    "Mastodon",
    "Twitter",
    "Python",
    "Golang",
    "Java",
    "Shell",
    "Perl",
    "TCL",
    "Ruby",
    "nodejs",
    "npm",
    "pip",
    "PSF",
    "FSF",
    "OSI",
    "free software",
    "software libre",
    "open source",
    "arduino",
    "GitHub",
    "GitLab",
    "raspberrypi",
    "NVIDIA",
    "ATX",
    "BSD",
    "kubernetes",
    "k8s",
    "malware",
    "privacy",
    "PGP",
    "GPG",
    "OpenSSL",
    "curl",
    "Solaris",
    "Sun",
    "Debian",
    "Joomla",
    "WordPress",
    "Mint",
    "Ubuntu",
    "Vulkan",
    "Wine",
    "KDE",
    "Plasma",
    "Kirigami",
    "GTK",
    "Gnome",
    "Xorg",
    "Wayland",
    "javascript",
    "react",
    "android",
    "iphone",
    "macbook",
    "signal",
    "amazon",
    "facebook",
    "google",
    "bitcoin",
    "crypto",
    "co-pilot",
    "CUDA",
    "microservices",
    "helm",
    "kubectl",
    "GC",
    "Garbage Collector",
    "llama",
    "pyscript",
    "WebAssembly",
    "JSON",
    "JWT",
    "API",
    "Azure",
    "AWS",
    "GCP",
    "OpenStack",
    "Red Hat",
    "RedHat",
    "OpenShift",
    "Suse",
    "Haskell",
    "WebKit",
    "MP4",
    "MPEG",
    "JPEG",
    "SVG",
    "Erlang",
    "Lisp",
    "ADA",
    "Turing",
    "CAD",
    "Wikipedia",
    "PHP",
    "sqlite3",
    "Elixir",
    "OCaml",
    "Clojure",
    "Scala",
    "Pascal",
    "C\+\+",
    "Rust",
    "C\#",
    "debug",
    "SCRUM",
    "Agile",
    "Kanban",
    "SQL",
    "jQuery",
    "Compose",
    "docker",
    "container",
    "podman",
    "rancher",
    "nerdctl",
    "limactl"
    ]

def getHtmlContent(link : str) -> str:
    response = requests.get(link)
    html_content = response.text
    return response.text

def getImageExtension(image_line: str) -> str:
    image = os.path.basename(image_line)
    return image.split('.')[-1]

def getImage(link : str) -> str:
    print('getimage() link:', link)
    response = requests.get(link)
    extension = getImageExtension(link)
    print('getimage() suffix:', extension)

    image_file = tempfile.mkstemp(suffix='.' + extension)
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
        print('Score:', score)
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
                print('Not related to something we might like, so we skip:', n['title'])
                continue
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

            print('translating:', n['title'])
            try:
                translated_summary = translator.translate(summary, src='en', dest='pt')
            except TypeError:
                # failed to translate, try the next one
                continue
            if len(translated_summary.text) < 5:
                print(' * failed...')
                continue
            translated_title = translator.translate(
                n['title'], src='en', dest='pt')

            content = translated_summary.text 
            content += "\n\nFonte: <a href=\"" + n['link']
            content += "\">" + n['link'] + "</a>"
 
            articles.append({
                'title': translated_title.text,
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

    def publishWordPress(self):

        # reference: https://github.com/crifan/crifanLibPython/blob/master/python3/crifanLib/thirdParty/crifanWordpress.py

        url = self.wordpress['site']
        token = self.wordpress['token']

        curHeaders = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        published_titles = self.getSiteRSSTitles()

        for art in self.articles:

            if art['title'] in published_titles:
                # skip if already there
                print('Article "' + art['title'] + '" already published')
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
                import re
                if not re.search('^http', art['image']):
                    link = art['link']
                    if link[-1]  == '/':
                        link = link[:-1]
                    art['image'] = '/'.join([ link, art['image'] ])
                print('image:', art['image'])
                image_path = getImage(art['image'])
                print('image_path:', image_path)
                with open(image_path, "rb") as f:
                    image_data = f.read()
                image_type = getImageExtension(image_path)
                image_filename = os.path.basename(image_path)

                print('image_filename:', image_filename)
                print('image_type:', image_type)

                media_headers = {
                    "Authorization": "Bearer " + token,
                    "Content-Disposition": "attachment; filename={}".format(image_filename),
                    "Cache-control" : "no-cache",
                    "Content-type" : "image/" + image_type
                }

                media_response = requests.post(url + "/wp-json/wp/v2/media", headers=media_headers, data=image_data)

                print('media_response:', media_response.text)
                if media_response.status_code == 200 or media_response.status_code == 201:
                    media_id = media_response.json()["id"]
                    data["featured_media"] = media_id
                print('removing image:", image_path)
                os.unlink(image_path)

            resp = requests.post(
                f"{url}/wp-json/wp/v2/posts",
                headers=curHeaders,
                # data=json.dumps(postDict),
                json=data, # internal auto do json.dumps
            )
            if resp.status_code == 200 or resp.status_code == 201:
                print('Posted:', art['title'])
            else:
                print('FAILED:', art['title'])
            print(' * status code:', resp.status_code)
            print(' * resp text:', resp.text)


    def run(self):
        self.getHackerNews()
        prettyprint(self.articles)

        self.articles = self.getArticles()
        prettyprint(self.articles)

        self.publishWordPress()


if __name__ == '__main__':
    print(time.ctime())
    news = NewsBot()
    news.run()
