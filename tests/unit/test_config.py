from pipeline.config import Settings


def test_a_template_placeholder_is_never_an_allowed_origin():
    s = Settings(cors_origins="https://tachyon-news.vercel.app", vercel_url="https://your-app.vercel.app")
    assert s.cors_origin_list == ["https://tachyon-news.vercel.app"]
    # A real address in the deprecated setting is still honoured.
    s = Settings(cors_origins="https://tachyon-news.vercel.app", vercel_url="https://stock-news-chi.vercel.app/")
    assert s.cors_origin_list == ["https://tachyon-news.vercel.app", "https://stock-news-chi.vercel.app"]
