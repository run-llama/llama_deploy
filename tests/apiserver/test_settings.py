from llama_deploy.apiserver.settings import ApiserverSettings


def test_settings_url() -> None:
    s = ApiserverSettings()
    assert s.url == "http://127.0.0.1:4501"

    s = ApiserverSettings(use_tls=True)
    assert s.url == "https://127.0.0.1:4501"

    s = ApiserverSettings(host="example.com", port=8080)
    assert s.url == "http://example.com:8080"

    s = ApiserverSettings(host="example.com", port=80)
    assert s.url == "http://example.com"
