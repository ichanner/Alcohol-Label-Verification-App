"""Regenerates labelcheck/countries.py from the mledoze/countries dataset.

Usage, from the repo root:

    python scripts/make_country_aliases.py --fetch   # download + regenerate
    python scripts/make_country_aliases.py           # regenerate from /tmp copy

The dataset (https://github.com/mledoze/countries, ODbL 1.0) is the data
behind restcountries.com: official name, common name and alternate spellings
for 250 countries — which is how "Holland", "Deutschland" and "Burma" resolve
to the same countries as "Netherlands", "Germany" and "Myanmar".

Every name is normalized with the same _clean() the verifier uses at runtime,
so lookups can never disagree with the comparison code. An alias that maps to
more than one country is dropped as ambiguous.
"""

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labelcheck.verify import _clean  # noqa: E402

SOURCE_URL = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
CACHE = Path("/tmp/countries.json")
TARGET = ROOT / "labelcheck" / "countries.py"

# spellings people actually type that the dataset doesn't carry
EXTRAS = {
    "america": "United States",
    "u s": "United States",        # "U. S." after punctuation cleaning
    "us": "United States",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
}

HEADER = '''\
"""Country name aliases -> canonical (common) name. GENERATED FILE.

Built by scripts/make_country_aliases.py from the mledoze/countries dataset
(https://github.com/mledoze/countries, Open Database License 1.0). Keys are
normalized with verify._clean() + casefold; values are the dataset's common
names. Regenerate with:  python scripts/make_country_aliases.py --fetch
"""

COUNTRY_ALIASES = {
'''


def main() -> None:
    if "--fetch" in sys.argv or not CACHE.exists():
        print(f"fetching {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, CACHE)
    countries = json.loads(CACHE.read_text())

    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()
    for country in countries:
        canonical = country["name"]["common"]
        names = {country["name"]["common"], country["name"]["official"],
                 *(s for s in country["altSpellings"] if len(s) >= 3)}
        for name in names:
            key = _clean(name).casefold()
            if not key:
                continue
            if aliases.get(key, canonical) != canonical:
                ambiguous.add(key)
            aliases[key] = canonical
    for key in ambiguous:
        del aliases[key]
    aliases.update(EXTRAS)

    lines = [f"    {key!r}: {canonical!r},\n"
             for key, canonical in sorted(aliases.items())]
    TARGET.write_text(HEADER + "".join(lines) + "}\n")
    print(f"wrote {TARGET}: {len(aliases)} aliases for "
          f"{len(countries)} countries ({len(ambiguous)} ambiguous dropped)")


if __name__ == "__main__":
    main()
