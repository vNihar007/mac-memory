"""
Search-quality evaluation harness for mac-memory.

NOT a unit test — this hits the live ChromaDB + Gemini API and measures
real retrieval quality against ground-truth queries.

Run:  cd src && python -m test_folder.eval_search
  or: cd src/test_folder && python eval_search.py

Each GROUND_TRUTH entry maps a natural-language query to the filename(s)
that *should* surface. We report:
  - rank of the first expected hit (1 = perfect)
  - precision@1  (did the #1 result match an expected file?)
  - recall@k     (did any expected file appear in top-k?)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mac_memory.search import search_files

TOP_K = 5

# query -> list of acceptable filenames (substring match, case-insensitive)
GROUND_TRUTH = {
    "a photo of a cat":            ["cat.jpeg", "wild_cat_spynx.jpeg"],
    "dog":                         ["dog .jpeg"],
    "rabbit":                      ["rabbit.jpeg"],
    "red panda":                   ["red_panda.jpeg"],
    "gorilla":                     ["gorilla.jpeg", "gorilla_like_person.jpeg"],
    "fish":                        ["fish.jpeg"],
    "raccoon":                     ["racoon .jpeg"],
    "my resume":                   ["resume.txt"],
    "invoice and billing":         ["invoice.txt"],
    "course completion certificate": ["NPTEL_certificate.pdf"],
    "house warming invitation":    ["Cream and Orange Griha Pravesh Invitation.png"],
}


def _matches(name: str, expected: list[str]) -> bool:
    n = name.lower()
    return any(e.lower() in n or n in e.lower() for e in expected)


def run():
    total = len(GROUND_TRUTH)
    p_at_1 = 0
    recall_at_k = 0
    ranks = []

    print(f"\n{'='*70}\n  SEARCH QUALITY EVAL  (top_k={TOP_K})\n{'='*70}")

    for query, expected in GROUND_TRUTH.items():
        results = search_files(query, top_k=TOP_K)
        names = [r.name for r in results]
        sims = [r.similarity for r in results]

        # rank of first expected hit
        rank = None
        for i, name in enumerate(names, 1):
            if _matches(name, expected):
                rank = i
                break

        hit_1 = bool(names) and _matches(names[0], expected)
        hit_k = rank is not None
        p_at_1 += int(hit_1)
        recall_at_k += int(hit_k)
        if rank:
            ranks.append(rank)

        status = "✅" if hit_1 else ("🔶" if hit_k else "❌")
        rank_str = f"rank {rank}" if rank else "MISS"
        top_sim = f"{sims[0]:.1%}" if sims else "—"
        print(f"\n{status} {query!r}  [{rank_str}, top_sim={top_sim}]")
        print(f"    expected: {expected}")
        for i, (name, sim) in enumerate(zip(names, sims), 1):
            mark = "←" if _matches(name, expected) else " "
            print(f"    {i}. {sim:5.1%}  {name} {mark}")

    print(f"\n{'='*70}\n  SUMMARY\n{'='*70}")
    print(f"  precision@1 : {p_at_1}/{total}  ({p_at_1/total:.0%})")
    print(f"  recall@{TOP_K}    : {recall_at_k}/{total}  ({recall_at_k/total:.0%})")
    if ranks:
        print(f"  mean rank   : {sum(ranks)/len(ranks):.2f}  (of hits)")
    print()


if __name__ == "__main__":
    run()
