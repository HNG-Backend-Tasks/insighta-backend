from app.parser import parse_query


def test_young_males():
    result = parse_query("young males")
    assert result == {"gender": "male", "min_age": 16, "max_age": 24}


def test_females_above_30():
    result = parse_query("females above 30")
    assert result == {"gender": "female", "min_age": 30}


def test_people_from_angola():
    result = parse_query("people from angola")
    assert result == {"country_id": "AO"}


def test_adult_males_from_kenya():
    result = parse_query("adult males from kenya")
    assert result == {
        "gender": "male",
        "age_group": "adult",
        "min_age": 20,
        "max_age": 59,
        "country_id": "KE",
    }


def test_male_and_female_teenagers_above_17():
    result = parse_query("male and female teenagers above 17")
    assert result == {"age_group": "teenager", "min_age": 17, "max_age": 19}


def test_empty_string():
    assert parse_query("") == {}


def test_whitespace_only():
    assert parse_query("   ") == {}


def test_gibberish():
    assert parse_query("foo bar baz") == {}


def test_both_genders_no_gender_filter():
    result = parse_query("males and females from nigeria")
    assert "gender" not in result
    assert result["country_id"] == "NG"


def test_above_without_number():
    result = parse_query("females above")
    assert "min_age" not in result
    assert result == {"gender": "female"}


def test_multi_word_country():
    result = parse_query("adults from south africa")
    assert result["country_id"] == "ZA"


def test_case_insensitive():
    result = parse_query("MALES FROM NIGERIA")
    assert result == {"gender": "male", "country_id": "NG"}


def test_young_maps_to_age_range_not_age_group():
    result = parse_query("young females")
    assert "age_group" not in result
    assert result["min_age"] == 16
    assert result["max_age"] == 24
