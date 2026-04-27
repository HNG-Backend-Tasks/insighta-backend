import unicodedata
from typing import Union

GENDER_MAP = {
    "male": "male",
    "males": "male",
    "man": "male",
    "men": "male",
    "guys": "male",
    "female": "female",
    "females": "female",
    "woman": "female",
    "women": "female",
}

AGE_GROUP_MAP = {
    "child": (0, 12),
    "children": (0, 12),
    "teen": (13, 19),
    "teenager": (13, 19),
    "teenagers": (13, 19),
    "adult": (20, 59),
    "adults": (20, 59),
    "senior": (60, 120),
    "seniors": (60, 120),
}

SPECIAL_AGE_WORDS = {
    "young": (16, 24),
}

ABOVE_WORDS = {"above", "over", "older"}
BELOW_WORDS = {"below", "under", "younger"}


COUNTRY_MAP = {
    "algeria": "DZ",
    "angola": "AO",
    "australia": "AU",
    "benin": "BJ",
    "botswana": "BW",
    "brazil": "BR",
    "burkina faso": "BF",
    "burundi": "BI",
    "cameroon": "CM",
    "canada": "CA",
    "cape verde": "CV",
    "central african republic": "CF",
    "chad": "TD",
    "china": "CN",
    "comoros": "KM",
    "cote d'ivoire": "CI",
    "ivory coast": "CI",
    "dr congo": "CD",
    "congo": "CD",  # pragmatic shortcut
    "republic of the congo": "CG",
    "djibouti": "DJ",
    "egypt": "EG",
    "equatorial guinea": "GQ",
    "eritrea": "ER",
    "eswatini": "SZ",
    "ethiopia": "ET",
    "france": "FR",
    "gabon": "GA",
    "gambia": "GM",
    "germany": "DE",
    "ghana": "GH",
    "guinea": "GN",
    "guinea-bissau": "GW",
    "india": "IN",
    "japan": "JP",
    "kenya": "KE",
    "lesotho": "LS",
    "liberia": "LR",
    "libya": "LY",
    "madagascar": "MG",
    "malawi": "MW",
    "mali": "ML",
    "mauritania": "MR",
    "mauritius": "MU",
    "morocco": "MA",
    "mozambique": "MZ",
    "namibia": "NA",
    "niger": "NE",
    "nigeria": "NG",
    "rwanda": "RW",
    "senegal": "SN",
    "seychelles": "SC",
    "sierra leone": "SL",
    "somalia": "SO",
    "south africa": "ZA",
    "south sudan": "SS",
    "sudan": "SD",
    "sao tome and principe": "ST",
    "tanzania": "TZ",
    "togo": "TG",
    "tunisia": "TN",
    "uganda": "UG",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "usa": "US",
    "western sahara": "EH",
    "zambia": "ZM",
    "zimbabwe": "ZW",
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def parse_query(query: str) -> dict[str, Union[str, int, list[str]]]:
    if not query or not query.strip():
        return {}

    query = _normalize(query)
    tokens = query.split()

    filters: dict = {}
    genders = set()

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in GENDER_MAP:
            genders.add(GENDER_MAP[token])

        elif token in AGE_GROUP_MAP:
            min_age, max_age = AGE_GROUP_MAP[token]
            filters["age_group"] = token.rstrip("s")  # normalize plural
            filters["min_age"] = min_age
            filters["max_age"] = max_age

        elif token in SPECIAL_AGE_WORDS:
            min_age, max_age = SPECIAL_AGE_WORDS[token]
            filters["min_age"] = min_age
            filters["max_age"] = max_age

        elif token in ABOVE_WORDS and i + 1 < len(tokens):
            if tokens[i + 1].isdigit():
                filters["min_age"] = int(tokens[i + 1])
                i += 1

        elif token in BELOW_WORDS and i + 1 < len(tokens):
            if tokens[i + 1].isdigit():
                filters["max_age"] = int(tokens[i + 1])
                i += 1

        elif token == "from" and i + 1 < len(tokens):
            # try bigram
            if i + 2 < len(tokens):
                bigram = f"{tokens[i + 1]} {tokens[i + 2]}"
                if bigram in COUNTRY_MAP:
                    filters["country_id"] = COUNTRY_MAP[bigram]
                    i += 2
                    continue

            # fallback single
            country = tokens[i + 1]
            if country in COUNTRY_MAP:
                filters["country_id"] = COUNTRY_MAP[country]
                i += 1

        i += 1

    if len(genders) == 1:
        filters["gender"] = list(genders)[0]

    if not filters:
        return {}

    return filters
