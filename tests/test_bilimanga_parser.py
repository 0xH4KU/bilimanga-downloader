from __future__ import annotations

from bilimanga_dl.sites.bilimanga import BilimangaParser

DETAIL_HTML = """
<html><body>
<h1 class="book-title">新世紀福音戰士 完全版</h1>
<span class="authorname"><a href="/author/貞本義行.html">貞本義行</a></span>
<span class="illname"><a href="/author/GAINAX.html">GAINAX</a></span>
<span class="tag-small-group origin-left">
  <a class="tag-small pink" href="/filter/a.html">科幻</a>
  <a class="tag-small gray" href="/filter/b.html">日本漫畫</a>
</span>
<section id="bookSummary"><content>西元2000年<br>第二次衝擊</content></section>
<ol class="module-slide-ol volchapters">
  <li><a href="/detail/285/vol_24417.html"><h3>新世紀福音戰士 完全版 7</h3></a></li>
  <li><a href="/detail/285/vol_24326.html"><h3>新世紀福音戰士 完全版 1</h3></a></li>
</ol>
</body></html>
"""


VOLUME_HTML = """
<html><body>
<h1 class="book-title">新世紀福音戰士 完全版 1</h1>
<h3 class="vol-title">新世紀福音戰士 完全版 1·目錄 <sum>(2)</sum></h3>
<ul class="module-content">
  <li class="chapter-li jsChapter">
    <a href="/read/285/24327.html" class="chapter-li-a">
      <span class="chapter-title">STAGE.１ 使徒、來襲</span>
    </a>
  </li>
  <li class="chapter-li jsChapter">
    <a href="/read/285/24328.html" class="chapter-li-a">
      <span class="chapter-title">STAGE.２ 再會⋯⋯</span>
    </a>
  </li>
</ul>
</body></html>
"""


READER_HTML = """
<html><body>
<script type="text/javascript">
var ReadParams={mangaid:'285',chapterid:'24327',chaptername:'第１卷 STAGE.１ 使徒、來襲'}
</script>
<div id="acontentz" class="bcontent">
  <img
    src="https://i.motiezw.com/0/285/24327/524971.avif"
    data-src="https://i.motiezw.com/0/285/24327/524971.avif"
    class="imagecontent lazyloaded">
  <img src="https://i.motiezw.com/0/285/24327/524972.avif" class="imagecontent">
  <img src="https://hm.baidu.com/hm.gif?ignored=1">
</div>
</body></html>
"""


def test_parse_detail_extracts_series_metadata_and_volumes() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    series = parser.parse_series_detail(DETAIL_HTML, "https://www.bilimanga.net/detail/285.html")

    assert series.manga_id == 285
    assert series.title == "新世紀福音戰士 完全版"
    assert series.authors == ["貞本義行", "GAINAX"]
    assert series.genres == ["科幻", "日本漫畫"]
    assert series.description == "西元2000年\n第二次衝擊"
    assert [volume.volume_id for volume in series.volumes] == [24326, 24417]
    assert series.volumes[0].title == "新世紀福音戰士 完全版 1"
    assert series.volumes[0].url == "https://www.bilimanga.net/detail/285/vol_24326.html"


def test_parse_volume_extracts_chapters() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    volume = parser.parse_volume(VOLUME_HTML, "https://www.bilimanga.net/detail/285/vol_24326.html")

    assert volume.manga_id == 285
    assert volume.volume_id == 24326
    assert volume.title == "新世紀福音戰士 完全版 1"
    assert [chapter.chapter_id for chapter in volume.chapters] == [24327, 24328]
    assert volume.chapters[0].title == "STAGE.１ 使徒、來襲"
    assert volume.chapters[0].url == "https://www.bilimanga.net/read/285/24327.html"


def test_parse_reader_extracts_only_chapter_image_urls() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    chapter = parser.parse_reader(READER_HTML, "https://www.bilimanga.net/read/285/24327.html")

    assert chapter.manga_id == 285
    assert chapter.chapter_id == 24327
    assert chapter.title == "第１卷 STAGE.１ 使徒、來襲"
    assert chapter.image_urls == [
        "https://i.motiezw.com/0/285/24327/524971.avif",
        "https://i.motiezw.com/0/285/24327/524972.avif",
    ]
