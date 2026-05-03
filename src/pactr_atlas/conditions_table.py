"""The 10 conditions and their matching keywords + MeSH terms.

LOCKED at prereg-v0.0.1. Any change requires a new prereg-v0.1.0-amend-N
tag and an entry in AMENDMENTS.md.
"""
from __future__ import annotations

CONDITIONS_10: dict[str, dict[str, list[str]]] = {
    "tuberculosis": {
        "keywords_strict": ["tuberculosis", "tuberculous"],
        "keywords_fuzzy": ["mycobacterium tuberculosis", "tb infection"],
        "mesh": ["D014376", "D014374"],
    },
    "hiv": {
        "keywords_strict": ["hiv", "human immunodeficiency virus"],
        "keywords_fuzzy": ["aids"],
        "mesh": ["D015658", "D000163"],
    },
    "sickle cell": {
        "keywords_strict": ["sickle cell", "sickle-cell"],
        "keywords_fuzzy": ["hbss", "hbsc"],
        "mesh": ["D000755"],
    },
    "schistosomiasis": {
        "keywords_strict": ["schistosomiasis", "bilharzia"],
        "keywords_fuzzy": ["schistosoma"],
        "mesh": ["D012552"],
    },
    "maternal sepsis": {
        "keywords_strict": ["maternal sepsis", "postpartum haemorrhage", "postpartum hemorrhage"],
        "keywords_fuzzy": ["puerperal sepsis", "obstetric sepsis"],
        "mesh": ["D006473"],
    },
    "neonatal sepsis": {
        "keywords_strict": ["neonatal sepsis"],
        "keywords_fuzzy": ["newborn sepsis", "neonatal infection"],
        "mesh": ["D000071074"],
    },
    "snakebite": {
        "keywords_strict": ["snakebite", "snake bite"],
        "keywords_fuzzy": ["envenoming", "antivenom"],
        "mesh": ["D012909"],
    },
    "soil-transmitted helminths": {
        "keywords_strict": ["soil-transmitted helminths", "soil transmitted helminths"],
        "keywords_fuzzy": ["ascaris", "trichuris", "hookworm"],
        "mesh": ["D006373"],
    },
    "cervical cancer": {
        "keywords_strict": ["cervical cancer", "cervical neoplasm"],
        "keywords_fuzzy": ["hpv vaccine", "cervical screening"],
        "mesh": ["D002583"],
    },
    "cholera": {
        "keywords_strict": ["cholera"],
        "keywords_fuzzy": ["vibrio cholerae"],
        "mesh": ["D002771"],
    },
}
