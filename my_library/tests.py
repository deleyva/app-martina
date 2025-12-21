from cms.models import ScorePage
from my_library.models import LibraryItem


def test_library_item_get_related_scorepage_media_no_score():
    item = LibraryItem()
    item.get_related_scorepage = lambda: None

    media = item.get_related_scorepage_media()
    assert media == {
        "score": None,
        "audios": [],
        "embeds": [],
    }


def test_library_item_get_related_scorepage_media_with_score():
    class DummyScore:
        def get_audios(self):
            return ["a1"]

        def get_embeds(self):
            return ["e1"]

    item = LibraryItem()
    item.get_related_scorepage = lambda: DummyScore()

    media = item.get_related_scorepage_media()
    assert media["score"] is not None
    assert media["audios"] == ["a1"]
    assert media["embeds"] == ["e1"]


def test_score_page_get_embed_html_for_url_only_when_in_score(monkeypatch):
    score = ScorePage.__new__(ScorePage)
    monkeypatch.setattr(score, "get_embeds", lambda: ["https://example.com/embed"])

    class DummyEmbed:
        html = "<iframe>OK</iframe>"

    monkeypatch.setattr("cms.models.get_embed", lambda url: DummyEmbed())

    assert (
        score.get_embed_html_for_url("https://example.com/embed")
        == "<iframe>OK</iframe>"
    )
    assert score.get_embed_html_for_url("https://example.com/other") == ""
