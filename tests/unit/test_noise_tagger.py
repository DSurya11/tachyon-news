import pytest

from pipeline.noise.tagger import tag_article


@pytest.mark.parametrize(
    ("headline", "tag"),
    [
        ("SHAREHOLDER ALERT: Pomerantz Law Firm Investigates Claims On Behalf of Investors of X", "law_firm_loss"),
        ("CLASS ACTION REMINDER: Kessler Topaz Meltzer & Check, LLP Reminds Investors of Deadline", "law_firm_loss"),
        ("Levi & Korsinsky Notifies Shareholders of ACME", "law_firm_loss"),
        ("Company Declares Quarterly Dividend", "dividend_routine"),
        ("Acme Therapeutics Reports Inducement Grants Under Nasdaq Listing Rule 5635(c)(4)", "nasdaq_grant"),
        ("Acme Receives Nasdaq Deficiency Notice Regarding Minimum Bid Price", "nasdaq_compliance"),
        ("Acme stock outperforms the market despite losses", "stock_blurb"),
    ],
)
def test_noise_patterns(headline, tag):
    assert tag in tag_article(headline)


@pytest.mark.parametrize(
    "headline",
    ["Director John Doe Sells 5000 Shares", "Apple announces breakthrough in AI chips", "Federal Reserve keeps interest rates steady"],
)
def test_real_news_is_not_noise(headline):
    assert tag_article(headline) == []


def test_body_is_checked_when_given():
    assert tag_article("Acme update", body="The board declared a regular quarterly dividend.") == ["dividend_routine"]
