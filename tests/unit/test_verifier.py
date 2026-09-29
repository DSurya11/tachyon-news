from pipeline.extract.verifier import verify

BODY = (
    "Apple sold 100 million iPhones in Q3, generating $1,250 million in services. "
    "“This is our best quarter yet!” the CEO said — adding that margins hit 46.5%."
)


def test_passes_when_evidence_and_numbers_match():
    res = verify(BODY, '"This is our best quarter yet!" the CEO said', [{"value": "100 million"}])
    assert res.passed and res.evidence_found and res.numbers_missing == []
    assert res.note == "ok"


def test_typography_and_thousands_separators_are_normalised():
    res = verify(BODY, "This is our best quarter yet!\" the CEO said - adding", [{"value": "1250"}, {"value": "$1,250 million"}])
    assert res.passed


def test_elided_evidence_checks_each_fragment():
    assert verify(BODY, "Apple sold 100 million iPhones in Q3 ... the CEO said — adding that margins", []).passed
    assert not verify(BODY, "Apple sold 100 million iPhones in Q3 ... revenue collapsed dramatically overnight", []).passed


def test_fails_when_evidence_missing():
    res = verify(BODY, "Revenue collapsed dramatically", [{"value": "100 million"}])
    assert not res.passed and not res.evidence_found
    assert "evidence_not_found" in res.note


def test_fails_when_number_missing():
    res = verify(BODY, "", [{"value": "200 million"}, {"value": "46.5%"}])
    assert not res.passed
    assert res.numbers_missing == ["200 million"]


def test_number_digits_must_match_whole_tokens():
    assert verify(BODY, "", [{"value": "46"}]).numbers_missing == ["46"]  # 46.5 is not 46


def test_no_body_cannot_verify():
    res = verify(None, "anything", [])
    assert not res.passed and res.note == "no_body"


def test_swapped_inner_quotes_still_match():
    body = 'The special committee (the "Special Committee"), comprising of three independent directors, was formed.'
    assert verify(body, "The special committee (the 'Special Committee'), comprising of three independent directors", []).passed


def test_near_verbatim_quote_with_corrected_typo_matches():
    body = "Filings show HDFC Bank disguised interest payments to certain accouints as marketing expenses with the knowledge."
    assert verify(body, "HDFC Bank disguised interest payments to certain accounts as marketing expenses", []).passed


def test_fuzzy_match_does_not_accept_a_different_claim():
    body = "Filings show HDFC Bank disguised interest payments to certain accounts as marketing expenses with the knowledge."
    assert not verify(body, "HDFC Bank disguised interest payments to certain accounts as bribes paid to regulators", []).passed
