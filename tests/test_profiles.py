from app.service import get_profiles


def test_default_pagination_shape(db):
    result = get_profiles(db)
    assert result["page"] == 1
    assert result["limit"] == 10
    assert result["total"] == 6
    assert isinstance(result["data"], list)


def test_total_matches_seeded(db):
    result = get_profiles(db)
    assert result["total"] == 6


def test_filter_gender_male(db):
    result = get_profiles(db, gender="male")
    assert result["total"] == 3
    assert all(p.gender == "male" for p in result["data"])


def test_filter_gender_female(db):
    result = get_profiles(db, gender="female")
    assert result["total"] == 3
    assert all(p.gender == "female" for p in result["data"])


def test_filter_country_id(db):
    result = get_profiles(db, country_id="NG")
    assert result["total"] == 3
    assert all(p.country_id == "NG" for p in result["data"])


def test_filter_age_group(db):
    result = get_profiles(db, age_group="adult")
    assert result["total"] == 3
    assert all(p.age_group == "adult" for p in result["data"])


def test_filter_min_age(db):
    result = get_profiles(db, min_age=30)
    assert all(p.age >= 30 for p in result["data"])


def test_filter_max_age(db):
    result = get_profiles(db, max_age=20)
    assert all(p.age <= 20 for p in result["data"])


def test_filter_min_gender_probability(db):
    result = get_profiles(db, min_gender_probability=0.90)
    assert all(p.gender_probability >= 0.90 for p in result["data"])


def test_filter_min_country_probability(db):
    result = get_profiles(db, min_country_probability=0.80)
    assert all(p.country_probability >= 0.80 for p in result["data"])


def test_combined_gender_and_country(db):
    result = get_profiles(db, gender="male", country_id="NG")
    assert result["total"] == 2
    assert all(p.gender == "male" and p.country_id == "NG" for p in result["data"])


def test_combined_gender_age_group_country(db):
    result = get_profiles(db, gender="female", age_group="adult", country_id="NG")
    assert result["total"] == 1
    assert result["data"][0].name == "Ngozi Adeyemi"


def test_sort_by_age_asc(db):
    result = get_profiles(db, sort_by="age", order="asc")
    ages = [p.age for p in result["data"]]
    assert ages == sorted(ages)


def test_sort_by_age_desc(db):
    result = get_profiles(db, sort_by="age", order="desc")
    ages = [p.age for p in result["data"]]
    assert ages == sorted(ages, reverse=True)


def test_pagination_limit(db):
    result = get_profiles(db, limit=2, page=1)
    assert len(result["data"]) == 2
    assert result["limit"] == 2
    assert result["total"] == 6


def test_pagination_page_2(db):
    result = get_profiles(db, limit=2, page=2)
    assert result["page"] == 2
    assert len(result["data"]) == 2


def test_no_results_for_nonexistent_filter(db):
    result = get_profiles(db, country_id="JP")
    assert result["total"] == 0
    assert result["data"] == []
