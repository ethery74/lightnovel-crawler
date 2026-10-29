import logging
import re

from lncrawl.core import Chapter, LegacyCrawler, Volume
from lncrawl.core.models import SearchResult

logger = logging.getLogger(__name__)


class NovelFireCrawler(LegacyCrawler):
    search_url = "https://novelfire.net/search?keyword={}&type=title"
    base_url = [
        "https://novelfire.net/",
        "https://novelphoenix.com/",
    ]
    has_mtl = False
    has_manga = False
    can_search = True
    request_rate_limit = 3

    def _to_phoenix_url(self, url: str) -> str:
        """Remap NovelFire chapter paths directly to NovelPhoenix to avoid the broken redirect."""
        cleaned = url.replace(r"\/", "/").replace("\\", "")
        return cleaned.replace("novelfire.net/book/", "novelphoenix.com/novel/")

    def read_novel_info(self) -> None:
        soup = self.get_soup(self.novel_url)

        self.novel_title = soup.find("h1").text.strip()
        self.novel_author = soup.select_one('span[itemprop="author"]').text.strip()

        img = soup.select_one(".cover img")
        self.novel_cover = self.absolute_url(img["src"])

        vol_id = 1
        vol_url = self.novel_url.rstrip("/") + "/chapters"

        while vol_url:
            soup = self.get_soup(self.absolute_url(vol_url))

            chapters = soup.select("ul.chapter-list li a")
            for a in chapters:
                chap_id = len(self.chapters) + 1
                raw_url = self.absolute_url(a["href"])
                
                # Convert to direct novelphoenix URL
                direct_url = self._to_phoenix_url(raw_url)

                self.chapters.append(
                    Chapter(
                        id=chap_id,
                        volume=vol_id,
                        title=a.get("title") or a.text.strip(),
                        url=direct_url,
                    )
                )

            self.volumes.append(Volume(id=vol_id))

            next_vol_a = soup.select_one("a.page-link[rel='next']")
            if next_vol_a and next_vol_a.get("href"):
                vol_url = next_vol_a["href"]
                vol_id += 1
            else:
                vol_url = False
                break

    def download_chapter_body(self, chapter) -> str:
        chap_url = chapter["url"] if isinstance(chapter, dict) else chapter.url
        chap_url = self._to_phoenix_url(chap_url)

        soup = self.get_soup(chap_url)
        contents = soup.select_one("div#content")
        if not contents:
            return ""

        # Remove duplicate headers at top of chapter
        elements_to_check = contents.find_all(True)[:5]
        for element in elements_to_check:
            element_text = element.get_text(" ", strip=True)
            if not element_text:
                continue

            if re.match(r"(?i)^\s*chapter\s+\d+", element_text):
                element.decompose()

        return self.cleaner.extract_contents(contents)

    def search_novel(self, query):
        query = query.lower().replace(" ", "+")
        soup = self.get_soup(self.search_url.format(query))

        results = []
        for item in soup.select("ul.novel-list li.novel-item"):
            a = item.select_one("a")

            title = a.get("title")
            url = self.absolute_url(a.get("href"))

            chapters = a.select_one(".icon-book-open").text
            rank = a.select_one(".icon-crown").text
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    info=f"{chapters} | {rank}",
                )
            )

        return results
