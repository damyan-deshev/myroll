import json
from collections import Counter
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[2] / "bundled" / "quick_npc_seeds" / "quick_npc_seeds.json"

REQUIRED_KEYS = {
    "id",
    "type",
    "race",
    "gender",
    "name",
    "role",
    "origin",
    "appearance",
    "voice",
    "mannerism",
    "attitude",
    "tiny_backstory",
    "hook_or_secret",
    "portrait_tags",
    "use_tags",
}

EXPECTED_TYPE_COUNTS = {
    "guard_soldier": 25,
    "commoner_villager": 25,
    "merchant_trader": 25,
    "artisan_craftsperson": 25,
    "noble_official_bureaucrat": 25,
    "criminal_spy_smuggler": 25,
    "scholar_scribe_priest": 25,
    "traveler_refugee_pilgrim": 25,
    "wilderness_local_guide_hunter": 25,
    "sailor_porter_caravan_worker": 25,
    "cultist_zealot_secret_believer": 25,
    "weird_magical_stranger": 25,
}

ALLOWED_RACES = {
    "Aarakocra",
    "Aasimar",
    "Air Genasi",
    "Bugbear",
    "Centaur",
    "Changeling",
    "Deep Gnome",
    "Dragonborn",
    "Drow",
    "Dwarf",
    "Earth Genasi",
    "Elf",
    "Fairy",
    "Firbolg",
    "Fire Genasi",
    "Gnome",
    "Goblin",
    "Goliath",
    "Halfling",
    "Harengon",
    "Hobgoblin",
    "Human",
    "Kenku",
    "Kobold",
    "Lizardfolk",
    "Orc",
    "Satyr",
    "Shadar-kai",
    "Tabaxi",
    "Tiefling",
    "Triton",
    "Water Genasi",
}

ALLOWED_GENDERS = {"female", "male"}


def test_quick_npc_seed_catalog_schema_and_distribution():
    seeds = json.loads(CATALOG_PATH.read_text())

    assert len(seeds) == 300
    assert Counter(seed["type"] for seed in seeds) == EXPECTED_TYPE_COUNTS

    ids = [seed["id"] for seed in seeds]
    assert len(ids) == len(set(ids))

    names = [seed["name"] for seed in seeds]
    assert len(names) == len(set(names))

    for seed in seeds:
        assert set(seed) == REQUIRED_KEYS
        assert seed["id"].startswith("quick_npc_")
        assert seed["type"] in EXPECTED_TYPE_COUNTS
        assert seed["race"] in ALLOWED_RACES
        assert seed["gender"] in ALLOWED_GENDERS

        for key in REQUIRED_KEYS - {"portrait_tags", "use_tags"}:
            assert isinstance(seed[key], str)
            assert seed[key].strip()

        assert isinstance(seed["portrait_tags"], list)
        assert seed["portrait_tags"]
        assert all(isinstance(tag, str) and tag.strip() for tag in seed["portrait_tags"])

        assert isinstance(seed["use_tags"], list)
        assert seed["use_tags"]
        assert all(isinstance(tag, str) and tag.strip() for tag in seed["use_tags"])
