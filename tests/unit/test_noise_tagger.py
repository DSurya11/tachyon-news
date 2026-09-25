from pipeline.noise.tagger import tag_article

def test_noise_tagger_law_firm():
    tags = tag_article("SHAREHOLDER ALERT: Pomerantz Law Firm Investigates Claims On Behalf of Investors of X")
    assert "law_firm_loss" in tags
    
    tags2 = tag_article("CLASS ACTION REMINDER: Kessler Topaz Meltzer & Check, LLP Reminds Investors of Deadline")
    assert "law_firm_loss" in tags2

def test_noise_tagger_dividend():
    tags = tag_article("Company Declares Quarterly Dividend")
    assert "dividend_routine" in tags

def test_noise_tagger_insider():
    # Insider sales are not currently tagged by the noise tagger patterns, they're valid
    tags = tag_article("Director John Doe Sells 5000 Shares")
    assert not tags
    
def test_noise_tagger_real_news():
    tags = tag_article("Apple announces breakthrough in AI chips")
    assert not tags
    
    tags2 = tag_article("Federal Reserve keeps interest rates steady")
    assert not tags2
