#!/usr/bin/env python3
"""Write a curated publisher authority list for citation matching."""

import json
from pathlib import Path


OUTPUT_PATH = Path("active_data/publishers.json")


PUBLISHERS = [
    {
        "publisher": "Oxford University Press",
        "aliases": ["OUP", "Oxford Univ. Press", "Oxford U.P.", "Clarendon Press"],
    },
    {
        "publisher": "Cambridge University Press",
        "aliases": ["CUP", "Cambridge Univ. Press", "Cambridge U.P."],
    },
    {
        "publisher": "Princeton University Press",
        "aliases": ["Princeton Univ. Press", "Princeton U.P."],
    },
    {
        "publisher": "Harvard University Press",
        "aliases": ["Harvard Univ. Press", "Harvard U.P."],
    },
    {
        "publisher": "Columbia University Press",
        "aliases": ["Columbia Univ. Press", "Columbia U.P."],
    },
    {
        "publisher": "University of Chicago Press",
        "aliases": ["Chicago University Press", "Univ. of Chicago Press"],
    },
    {
        "publisher": "Yale University Press",
        "aliases": ["Yale Univ. Press", "Yale U.P."],
    },
    {
        "publisher": "MIT Press",
        "aliases": ["The MIT Press", "M.I.T. Press", "Massachusetts Institute of Technology Press"],
    },
    {
        "publisher": "Springer",
        "aliases": ["Springer-Verlag", "Springer Verlag", "Springer, Berlin"],
    },
    {
        "publisher": "B. G. Teubner",
        "aliases": ["Teubner", "B.G. Teubner", "B. G. Teubner Verlag"],
    },
    {
        "publisher": "Walter de Gruyter",
        "aliases": ["De Gruyter", "Walter de Gruyter & Co.", "W. de Gruyter"],
    },
    {
        "publisher": "J. C. B. Mohr (Paul Siebeck)",
        "aliases": ["Mohr Siebeck", "J.C.B. Mohr", "Paul Siebeck"],
    },
    {
        "publisher": "S. Hirzel",
        "aliases": ["Hirzel", "S. Hirzel Verlag"],
    },
    {
        "publisher": "Hermann et Cie",
        "aliases": ["Hermann & Cie", "Hermann", "Librairie Hermann"],
    },
    {
        "publisher": "Félix Alcan",
        "aliases": ["F. Alcan", "Felix Alcan", "Librairie Félix Alcan"],
    },
    {
        "publisher": "Presses Universitaires de France",
        "aliases": ["PUF", "Presses universitaires de France"],
    },
    {
        "publisher": "Gauthier-Villars",
        "aliases": ["Gauthier Villars", "Gauthier-Villars et Cie"],
    },
    {
        "publisher": "Librairie Armand Colin",
        "aliases": ["Armand Colin"],
    },
    {
        "publisher": "Dunod",
        "aliases": ["Dunod éditeur", "Dunod Editeur"],
    },
    {
        "publisher": "North-Holland Publishing Company",
        "aliases": ["North-Holland", "North Holland", "North-Holland Pub. Co."],
    },
    {
        "publisher": "Elsevier",
        "aliases": ["Elsevier Publishing Company", "Elsevier Science"],
    },
    {
        "publisher": "D. Reidel Publishing Company",
        "aliases": ["Reidel", "D. Reidel", "D. Reidel Publishing Co."],
    },
    {
        "publisher": "Pergamon Press",
        "aliases": ["Pergamon"],
    },
    {
        "publisher": "Dover Publications",
        "aliases": ["Dover", "Dover Publications, Inc."],
    },
    {
        "publisher": "Interscience Publishers",
        "aliases": ["Interscience", "Interscience Publishers, Inc."],
    },
    {
        "publisher": "John Wiley & Sons",
        "aliases": ["Wiley", "John Wiley", "Wiley & Sons"],
    },
    {
        "publisher": "McGraw-Hill",
        "aliases": ["McGraw Hill", "McGraw-Hill Book Company"],
    },
    {
        "publisher": "Prentice-Hall",
        "aliases": ["Prentice Hall", "Prentice-Hall, Inc."],
    },
    {
        "publisher": "Addison-Wesley",
        "aliases": ["Addison Wesley", "Addison-Wesley Publishing Company"],
    },
    {
        "publisher": "Van Nostrand",
        "aliases": ["D. Van Nostrand", "D. Van Nostrand Company"],
    },
    {
        "publisher": "Chelsea Publishing Company",
        "aliases": ["Chelsea", "Chelsea Publishing Co."],
    },
    {
        "publisher": "Macmillan",
        "aliases": ["The Macmillan Company", "Macmillan & Co.", "Macmillan Company"],
    },
    {
        "publisher": "Routledge & Kegan Paul",
        "aliases": ["Routledge and Kegan Paul", "Routledge", "Kegan Paul"],
    },
    {
        "publisher": "Kegan Paul, Trench, Trübner & Co.",
        "aliases": ["Kegan Paul, Trench, Trubner & Co.", "Kegan Paul, Trench, Trübner"],
    },
    {
        "publisher": "George Allen & Unwin",
        "aliases": ["Allen & Unwin", "G. Allen & Unwin"],
    },
    {
        "publisher": "Longmans, Green & Co.",
        "aliases": ["Longmans Green", "Longmans, Green, Reader & Dyer", "Longmans"],
    },
    {
        "publisher": "The Open Court Publishing Company",
        "aliases": ["Open Court", "Open Court Publishing Co.", "The Open Court Publishing Co."],
    },
    {
        "publisher": "Harcourt, Brace & Company",
        "aliases": ["Harcourt Brace", "Harcourt, Brace and Company", "Harcourt Brace & Co."],
    },
    {
        "publisher": "Simon & Schuster",
        "aliases": ["Simon and Schuster"],
    },
    {
        "publisher": "W. W. Norton & Company",
        "aliases": ["W. W. Norton", "Norton", "W.W. Norton"],
    },
    {
        "publisher": "Basic Books",
        "aliases": [],
    },
    {
        "publisher": "Blackwell",
        "aliases": ["Basil Blackwell", "B. Blackwell"],
    },
    {
        "publisher": "Methuen",
        "aliases": ["Methuen & Co.", "Methuen and Co."],
    },
    {
        "publisher": "Penguin Books",
        "aliases": ["Penguin", "Allen Lane"],
    },
    {
        "publisher": "Hafner Publishing Company",
        "aliases": ["Hafner", "Hafner Publishing Co."],
    },
    {
        "publisher": "Academic Press",
        "aliases": [],
    },
    {
        "publisher": "Akademie-Verlag",
        "aliases": ["Akademie Verlag"],
    },
    {
        "publisher": "Państwowe Wydawnictwo Naukowe",
        "aliases": ["PWN", "Panstwowe Wydawnictwo Naukowe"],
    },
    {
        "publisher": "Mir Publishers",
        "aliases": ["Mir"],
    },
    {
        "publisher": "Espasa-Calpe",
        "aliases": ["Espasa-Calpe, S. A.", "Espasa Calpe"],
    },
    {
        "publisher": "A. W. Sijthoff",
        "aliases": ["Sijthoff", "A.W. Sijthoff"],
    },
    {
        "publisher": "Otto Harrassowitz",
        "aliases": ["Harrassowitz", "O. Harrassowitz"],
    },
    {
        "publisher": "Walton & Maberly",
        "aliases": ["Walton and Maberly"],
    },
    {
        "publisher": "Taylor and Walton",
        "aliases": [],
    },
    {
        "publisher": "Edward Stanford",
        "aliases": [],
    },
]


def main():
    OUTPUT_PATH.write_text(
        json.dumps(PUBLISHERS, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(PUBLISHERS)} curated publisher records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
