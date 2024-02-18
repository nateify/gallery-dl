# -*- coding: utf-8 -*-

# Copyright 2018-2023 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extractors for https://www.livejournal.com/"""

from .common import Extractor, Message
from .. import text
import json
import re


class LiveJournalExtractor(Extractor):
    """Base class for LiveJournal extractors"""

    category = "livejournal"
    filename_fmt = "{category}_{journal[username]}_{id}_{num}.{extension}"
    archive_fmt = "{journal[username]}_{id}"
    root = "https://www.livejournal.com"

    def __init__(self, match):
        super().__init__(match)
        self.journal = None
        self.post_id = None

    def items(self):
        self.cookies.set("adult_explicit", "1", domain=".livejournal.com")
        data = self.get_metadata()

        for post_url in self.get_posts():
            post, urls = self.extract_post(post_url)

            yield Message.Directory, post

            for i, url in enumerate(urls, 1):
                post["num"] = i
                post["url"] = url

                yield Message.Url, url, post

    def get_metadata(self):
        """Return general metadata"""
        return {}

    def get_posts(self):
        """Return an iterable containing data of all relevant posts"""

    def extract_post(self, post_url):

        with self.request(post_url, fatal=False) as response:
            if response.status_code >= 400:
                return {}
            page = response.text

        article_element = re.search(r"<article[^>]*class=\" *b-singlepost[^>]*>(.*?)</article>", page, re.DOTALL)

        image_urls = []
        for img_match in re.finditer(
            r"<img[^>]*src=\"(https?://imgprx\.livejournal\.net/[^\"]+)[^>]*>", article_element.group(1), re.DOTALL
        ):
            image_url = img_match.group(1)
            image_urls.append(image_url)

        extr = text.extract_from(page)

        page_json = json.loads(extr("Site.page = ", "};") + "}")
        is_adult = bool(extr("Site.page.is_adult = ", ";"))
        journal_json = json.loads(extr("Site.journal = ", "};") + "}")
        entry_json = json.loads(extr("Site.entry = ", "};") + "}")
        journal_cur_json = json.loads(extr("Site.current_journal = ", "};") + "}")

        journal_keys_excl = {"public_entries", "is_journal_page", "manifest"}  # Unnecessary metadata
        journal_data = {k: v for k, v in journal_json.items() if k not in journal_keys_excl}

        journal_data["url_allpics"] = journal_cur_json["url_allpics"]
        journal_data["url_userpic"] = journal_cur_json["url_userpic"]
        journal_data["userpic_w"] = journal_cur_json["userpic_w"]

        poster_data = {k: v for k, v in entry_json.items() if k.startswith("poster")}

        data = {
            "url": post_url,
            "id": self.post_id,
            "journal": journal_data,
            "poster": poster_data,
            "title": entry_json["title"],
            "date": text.parse_timestamp(entry_json["eventtime"]),
            "replycount": page_json["replycount"],
            "allow_commenting": bool(page_json["allow_commenting"]),
            "is_adult": is_adult,
            "extension": None
        }

        return data, image_urls

    def _extract_images(self, page):
        return


class LiveJournalPostExtractor(LiveJournalExtractor):
    """Extractor for a single LiveJournal post"""

    subcategory = "post"
    pattern = r"(?:https?://)?([\w-]+)\.livejournal\.com/(\d+)\.html"
    example = "https://probertson.livejournal.com/46158.html"

    def __init__(self, match):
        LiveJournalExtractor.__init__(self, match)
        self.journal = match.group(1)
        self.post_id = match.group(2)

        self.post_url = "https://{}.livejournal.com/{}.html".format(self.journal, self.post_id)

    def get_posts(self):
        return (self.post_url,)
