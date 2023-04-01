#! /usr/bin/env python3

import feedparser
import hashlib
import requests
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from heapq import nlargest
import tempfile
import json
from googletrans import Translator
import dbm

HACKERNEWS_FEED = "https://hnrss.org/newest"

translator = Translator(service_urls=['translate.google.com'])

def hashData(line : str) -> str:
    return hashlib.sha256(line.encode('utf-8')).hexdigest()

def getHackerNews() -> list:
    '''
    get the news from rss and return as dict
    '''
    fp = feedparser.parse(HACKERNEWS_FEED)
    news_list = list()
    for e in fp['entries']:
        news_list.append({
            'title' : e['title'],
            'link' : e['link'],
            'id' : hashData(e['id'])
        })
    return news_list


def getHtmlContent(link : str) -> str:
    response = requests.get(link)
    html_content = response.text
    return response.text


def getArticles(news_list : list) -> list:
    '''
    Open each news from the list, fetch the data and try to generate a summary.
    If succeed, then add to the list.
    '''
    articles = list()
    for n in news_list:
        html_content = getHtmlContent(n['link'])
        soup = BeautifulSoup(html_content, "html.parser")

        article_text = ""
        for element in soup.select("article p"):
            article_text += "\n" + element.text

        try:
            sentences = sent_tokenize(article_text)
        except LookupError:
            print("initializing nltk")
            import nltk
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
            continue

        translated_summary = translator.translate(summary, src='en', dest='pt')
        translated_title = translator.translate(n['title'], src='en', dest='pt')

        img_tags = soup.find_all('img')
        img_url = None
        if img_tags:
            img_url = img_tags[0]['src']

        articles.append({
            'title' : translated_title.text,
            'summary': translated_summary.text,
            'link' : n['link'],
            'id' : n['id'],
            'image' : img_url
        })

    return articles


def getImage(link):
    response = requests.get(img_url)

    image_file = tempfile.mkstemp(prefix=jpg)
    with open(image_file, "wb") as f:
        f.write(response.content)

def prettyprint(data):
    if type(data) == dict():
        print(json.dumps(data, indent=4))
    elif type(data) == list():
        for e in data:
            prettyprint(e)
    else:
        print(data)


if __name__ == '__main__':
    print('Hello world')
    news = getHackerNews()
    prettyprint(news)

    articles = getArticles(news)
    prettyprint(articles)
