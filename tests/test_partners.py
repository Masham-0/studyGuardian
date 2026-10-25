import pytest

from studyguardian.audio import AudioError, speech_request, synthesize
from studyguardian.search import SearchError, is_reputable, parse_serp, search_learning_resources


def test_serp_parser_preserves_urls_and_prefers_edu():
    payload = {
        "organic_results": [
            {"title": "Random blog", "link": "https://example.com/post", "snippet": "maybe"},
            {"title": "Khan Academy", "link": "https://www.khanacademy.org/science/biology", "snippet": "osmosis"},
            {"title": "No link", "snippet": "skip"},
        ]
    }
    results = parse_serp(payload)
    assert results[0].url == "https://www.khanacademy.org/science/biology"
    assert results[0].reputable is True
    assert results[1].reputable is False
    assert is_reputable("https://openstax.org/books/biology-2e")
    assert [item.title for item in results] == ["Khan Academy", "Random blog"]


def test_missing_serpapi_key_does_not_call_network():
    class Session:
        def get(self, *args, **kwargs):
            raise AssertionError("network was called")

    with pytest.raises(SearchError) as caught:
        search_learning_resources("osmosis", None, session=Session())
    assert "SERPAPI_API_KEY" in str(caught.value)


def test_speech_payload_is_only_the_selected_text():
    request = speech_request("  Osmosis is diffusion of water.  ", "voice-1")
    assert request["json"] == {
        "text": "Osmosis is diffusion of water.",
        "model_id": "eleven_multilingual_v2",
    }
    assert "classroom" not in request["json"]["text"].lower()


def test_long_passage_is_refused_before_the_network():
    with pytest.raises(AudioError):
        speech_request("word " * 2000, "voice")


def test_missing_elevenlabs_key(tmp_path):
    class Session:
        def post(self, *args, **kwargs):
            raise AssertionError("network was called")

    with pytest.raises(AudioError) as caught:
        synthesize("Hello", None, "voice", tmp_path / "a.mp3", session=Session())
    assert "ELEVENLABS_API_KEY" in str(caught.value)


def test_audio_error_status(tmp_path):
    class Response:
        status_code = 401
        content = b""

    class Session:
        def post(self, url, headers, json, timeout):
            assert json["text"] == "Read this paragraph."
            assert "xi-api-key" in headers
            return Response()

    with pytest.raises(AudioError):
        synthesize("Read this paragraph.", "secret", "voice", tmp_path / "a.mp3", session=Session())
    assert not (tmp_path / "a.mp3").exists()
