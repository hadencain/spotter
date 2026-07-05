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


def test_normalize_never_strips_to_empty():
    assert normalize("Store 24") == "store 24"   # a real chain name, not a store-number suffix


def test_normalize_coerces_non_string():
    assert normalize(3) == "3"                   # dynamic-typed DB value must not crash


def test_classify_empty_defaults_to_chain():
    assert classify("") == "chain"
    assert classify(None) == "chain"


def test_classify_plural_and_british_venues():
    assert classify("Westfield Malls") == "venue"
    assert classify("City Centre") == "venue"
