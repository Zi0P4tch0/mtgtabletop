#!/usr/bin/env python

"""MTGTabletop v0.3.
Author: Matteo Pacini <m@matteopacini.me>.

Usage:
  mtgtabletop.py [-v] [--randomise-lands] DECK...
  mtgtabletop.py --version

Arguments:
  DECK                  One or more Magic: The Gathering deck in .dec format.

Options:
  -h --help             Show this screen.
  --version             Show version and exit.
  --randomise-lands     Randomise basic lands.
  -v --verbose          Print status messages.

"""
from docopt import docopt

###########
# Imports #
###########

import codecs
import io
import re
import urllib2

from bs4 import BeautifulSoup
from PIL import Image
from random import choice
from unidecode import unidecode
from urllib import quote


##############
# Exceptions #
##############

class UnavailableCardImageException(Exception):
    pass


def download_file(url):
    response = urllib2.urlopen(url)
    return response.read()


def is_basic_land(card_name):
    return card_name in ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']


def fetch_card_image_url(card_name):
    url = 'http://magiccards.info/query?q=%s' % quote(unidecode(card_name))
    html = download_file(url)
    soup = BeautifulSoup(html, 'html.parser')
    for link in soup.findAll('a', href=True):
        if link.string == card_name:
            tokens = link.attrs['href'][1:].replace('.html', '.jpg').split('/')
            return "http://magiccards.info/scans/%s/%s/%s" %\
                (tokens[1], tokens[0], tokens[2])
    return None


def fetch_basic_land_image_urls(card_name, verbose):
    url = 'http://magiccards.info/query?q=%s' % quote(card_name)
    html = download_file(url)
    soup = BeautifulSoup(html, 'html.parser')
    for link in soup.findAll('a', href=True):
        if link.string == card_name:
            regex = re.compile('\/[a-z0-9]+\/en\/[0-9a-b]+\.html')
            html = download_file(
                'http://magiccards.info%s' % link.attrs['href']
            )
            soup = BeautifulSoup(html, 'html.parser')
            urls = []
            small = soup.findAll('small')[0]
            for link in small.findAll('a', href=True):
                if regex.match(link.attrs['href']):
                    tokens = link.attrs['href'][1:]\
                        .replace('.html', '.jpg').split('/')
                    urls.append(
                        "http://magiccards.info/scans/%s/%s/%s" %
                        (tokens[1], tokens[0], tokens[2])
                    )
            if verbose:
                print "[VERBOSE] URLs found for card '%s':" % card_name
                for url in urls:
                    print "[VERBOSE] %s" % url
            return urls
    return None


def read_deck(fname):
    with codecs.open(fname, 'r', 'utf-8') as f:
        entries = []
        # Read lines, strip whitespaces and filter comments and empty lines.
        # TODO: Add support for the sideboard.
        lines = \
            [l.strip() for l in f.readlines() if not l.startswith('//')
                and not l.startswith('SB')]
        lines = filter(None, lines)
        # Parse deck entries.
        for line in lines:
            tokens = line.split(' ', 1)
            entries.append((int(tokens[0]), tokens[1]))
        return entries


def pretty_print_deck(entries):
    for entry in entries:
        print "%d x '%s'" % (entry[0], entry[1])


def fetch_image(url):
    try:
        return Image.open(io.BytesIO(
            download_file(url)
        ))
    except Exception:
        return None


def fetch_images(entries, randomise_lands, verbose):
    processed_entries = []
    for entry in entries:
        if is_basic_land(entry[1]) and randomise_lands:
            urls = fetch_basic_land_image_urls(entry[1], verbose)
            for i in range(0, entry[0]):
                chosen_url = choice(urls)
                if verbose:
                    print '[VERBOSE] Random lands (%s):' % entry[1]
                    print '[VERBOSE] Index %d URL %s' % (i, chosen_url)
                processed_entries.append((1, fetch_image(chosen_url)))
        else:
            if verbose:
                print "[VERBOSE] Fetching image for card '%s'..." % entry[1]
            url = fetch_card_image_url(entry[1])
            img = fetch_image(url)
            if not img:
                raise UnavailableCardImageException(
                    "Could not find an image for card: '%s'!" % entry[1]
                )
            processed_entries.append((entry[0], img))

    return processed_entries


def no_of_cards(entries):
    count = 0
    for entry in entries:
        count += entry[0]
    return count


def split_deck_if_necessary(entries):
    decks = []
    current_deck = []
    for entry in entries:
        if no_of_cards(current_deck) + entry[0] > 69:
            decks.append(current_deck)
            current_deck = []
        current_deck.append(entry)
    decks.append(current_deck)
    return decks


def stitch_deck(entries, output_fpath, verbose):

    CARDS_PER_ROW = 10
    CARDS_PER_COLUMN = 7
    CARD_WIDTH = 312
    CARD_HEIGHT = 445

    deck_face = Image.new(
        'RGB',
        (CARDS_PER_ROW * CARD_WIDTH, CARDS_PER_COLUMN * CARD_HEIGHT)
    )

    current_card_count = 1
    x = 0
    y = 0

    verbose_count = 0

    for entry in entries:
        for i in range(0, entry[0]):

            if verbose:
                verbose_count += 1

            deck_face.paste(entry[1], (x, y))

            if current_card_count % CARDS_PER_ROW == 0:
                x = 0
                y += CARD_HEIGHT
            else:
                x += CARD_WIDTH

            current_card_count += 1

    if verbose:
        print '[VERBOSE] Stiched images count: %d.' % verbose_count

    # Fetch and insert hidden card

    hidden_card = Image.open(io.BytesIO(
        download_file('http://itszn.com/mtg/cardback.jpg')
    ))
    hidden_card = hidden_card.resize(
        (CARD_WIDTH, CARD_HEIGHT), Image.ANTIALIAS
    )
    deck_face.paste(
        hidden_card,
        (CARD_WIDTH * (CARDS_PER_ROW - 1),
            (CARD_HEIGHT * (CARDS_PER_COLUMN - 1)))
    )

    deck_face.save(output_fpath, 'JPEG', quality=100)


def export_deck(entries, basename, verbose):
    decks = split_deck_if_necessary(entries)
    deck_count = 0
    for deck in decks:
        print 'Deck face n. %d size: %d.' % (deck_count, no_of_cards(deck))
        stitch_deck(
            deck,
            '%s_%d.jpg' % (basename, deck_count),
            verbose=verbose
        )
        deck_count += 1

if __name__ == '__main__':

    # Parse arguments.
    arguments = docopt(__doc__, version='0.3')

    verbose = arguments['--verbose']
    randomise_lands = arguments['--randomise-lands']

    # Process decks

    for deck in arguments['DECK']:

        print "Processing deck '%s'..." % deck

        entries = read_deck(deck)

        if verbose:
            pretty_print_deck(entries)

        print 'Fetching images... this may take a while!'

        try:
            entries = fetch_images(entries, randomise_lands, verbose)
        except UnavailableCardImageException as e:
            print '[ERROR] %s' % e
            continue

        print 'Exporting Tabletop Simulator deck faces...'

        export_deck(entries, deck.split('.', 1)[0], verbose)
