from pipeline.extract.verifier import verify

def test_verify_passes_when_evidence_and_numbers_match():
    body = "Apple sold 100 million iPhones in Q3. The CEO said 'This is our best quarter yet!'"
    
    res = verify(
        body=body,
        evidence="This is our best quarter yet!",
        numbers=[{"value": "100 million"}]
    )
    assert res.passed is True
    assert res.evidence_found is True
    assert len(res.numbers_missing) == 0

def test_verify_fails_evidence_missing():
    body = "Apple sold 100 million iPhones in Q3."
    
    res = verify(
        body=body,
        evidence="This is our best quarter yet!",
        numbers=[{"value": "100 million"}]
    )
    assert res.passed is False
    assert res.evidence_found is False

def test_verify_fails_number_missing():
    body = "Apple sold 50 million iPhones in Q3."
    
    res = verify(
        body=body,
        evidence="Apple sold 50 million",
        numbers=[{"value": "100 million"}]
    )
    assert res.passed is False
    assert "100 million" in res.numbers_missing

def test_verify_no_body_treats_as_neutral():
    res = verify(
        body=None,
        evidence="Any",
        numbers=[{"value": "100"}]
    )
    assert res.passed is False
    assert res.note == "no_body"
