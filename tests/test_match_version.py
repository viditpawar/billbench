from billbench.congress import match_version

VERSIONS = [
    {"type": "Introduced in House", "date": "2025-02-01T00:00:00Z"},
    {"type": "Reported in House", "date": "2025-06-10T00:00:00Z"},
    {"type": "Engrossed in House", "date": "2025-07-01T00:00:00Z"},
]


def test_exact_stage_match():
    v, m = match_version({"actionDesc": "Introduced in House", "actionDate": "2025-02-01"}, VERSIONS)
    assert (v["type"], m) == ("Introduced in House", "exact")


def test_passed_house_maps_to_engrossed():
    v, m = match_version({"actionDesc": "Passed House", "actionDate": "2025-07-01"}, VERSIONS)
    assert v["type"] == "Engrossed in House" and m == "exact"


def test_date_fallback_never_uses_future_text():
    v, m = match_version({"actionDesc": "Something Else", "actionDate": "2025-06-15"}, VERSIONS)
    assert v["type"] == "Reported in House" and m == "date_fallback"


def test_no_match():
    assert match_version({"actionDesc": "x", "actionDate": "2025-01-01"}, VERSIONS) == (None, None)
