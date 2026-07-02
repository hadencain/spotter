from entities import classify, normalize


def test_normalize_case_and_punctuation():
    assert normalize("  WALMART  ") == "walmart"
    assert normalize("T.J. Maxx") == "t j maxx"
    assert normalize("Sam's Club") == "sam's club"   # apostrophe and & survive
    assert normalize("H&M") == "h&m"


def test_normalize_strips_store_numbers():
    assert normalize("Walmart #4531") == "walmart"
    assert normalize("Target Store 45") == "target"
    assert normalize("Forever 21") == "forever 21"   # 2-digit brand number is kept


def test_normalize_empty_and_none():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_classify_venues():
    assert classify("Haywood Mall") == "venue"
    assert classify("Target Plaza") == "venue"
    assert classify("Sunvalley Shopping Center") == "venue"
    assert classify("Westfield Galleria") == "venue"


def test_classify_chains():
    assert classify("Target") == "chain"
    assert classify("Kay Outlet") == "chain"        # bare 'outlet' is NOT a venue word
    assert classify("Nordstrom") == "chain"
