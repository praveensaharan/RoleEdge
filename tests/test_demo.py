from roleedge.demo import CONTENT_CASES, FAMILIES, RECIPIENTS


def test_every_recipient_belongs_to_exactly_one_family():
    owners = {key: [f.id for f in FAMILIES.values() if key in f.recipients] for key in RECIPIENTS}
    assert all(len(found) == 1 for found in owners.values()), owners
    assert {case.recipient for case in CONTENT_CASES} <= set(RECIPIENTS)


def test_call_scenario_names_are_unique():
    names = [name for family in FAMILIES.values() for name in family.calls]
    assert len(names) == len(set(names))


def test_the_japanese_family_is_set_up_for_japan():
    japan = FAMILIES["japan"]
    assert japan.care_plan.emergency_number == "119" and japan.care_plan.parent.language == "Japanese"
    assert all(RECIPIENTS[key].timezone == "Asia/Tokyo" for key in japan.recipients)
    assert "lonely_day" in japan.calls


def test_japanese_text_samples_load():
    texts = {case.id: case.build().text for case in CONTENT_CASES if case.id in ("line_scam", "city_notice")}
    assert set(texts) == {"line_scam", "city_notice"}
    assert "ATM" in texts["line_scam"] and "11月20日" in texts["city_notice"]
