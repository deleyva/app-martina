from clases.models import ClassSessionItem
from clases.models import GroupLibraryItem


def test_group_library_item_get_related_scorepage_media_no_score():
    item = GroupLibraryItem()
    item.get_related_scorepage = lambda: None

    media = item.get_related_scorepage_media()
    assert media == {
        "score": None,
        "audios": [],
        "embeds": [],
    }


def test_group_library_item_get_related_scorepage_media_with_score():
    class DummyScore:
        def get_audios(self):
            return ["a1"]

        def get_embeds(self):
            return ["e1"]

    item = GroupLibraryItem()
    item.get_related_scorepage = lambda: DummyScore()

    media = item.get_related_scorepage_media()
    assert media["score"] is not None
    assert media["audios"] == ["a1"]
    assert media["embeds"] == ["e1"]


def test_class_session_item_get_related_scorepage_media_no_score():
    item = ClassSessionItem()
    item.get_related_scorepage = lambda: None

    media = item.get_related_scorepage_media()
    assert media == {
        "score": None,
        "audios": [],
        "embeds": [],
    }


def test_class_session_item_get_related_scorepage_media_with_score():
    class DummyScore:
        def get_audios(self):
            return ["a1"]

        def get_embeds(self):
            return ["e1"]

    item = ClassSessionItem()
    item.get_related_scorepage = lambda: DummyScore()

    media = item.get_related_scorepage_media()
    assert media["score"] is not None
    assert media["audios"] == ["a1"]
    assert media["embeds"] == ["e1"]
