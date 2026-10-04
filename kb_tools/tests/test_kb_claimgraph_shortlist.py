"""The unmarked-reference shortlist ranks in-test statements into the goldens held here."""

from kb_tools.kb_claimgraph import shortlist

#: Five claims of one small paper: two on the escape rate, three on firm growth.
PAPER = {
    "clm-a": "The escape rate $`\\lambda_c`$ falls as the barrier rises.",
    "clm-b": "Firm growth is monotone in capital.",
    "clm-c": "The barrier sets the escape rate:\n\n``` math\n\\lambda_{c} = e^{-\\Delta}\n```\n",
    "clm-d": "Capital accumulation drives firm growth.",
    "clm-e": "Zombie firm growth stalls.",
}


def ranked(statements, *, candidate_pairs=()):
    return shortlist.rank(statements, sources=list(statements), candidate_pairs=candidate_pairs)


def test_every_source_ranks_every_other_node_by_what_their_statements_share():
    assert ranked(PAPER) == {
        "clm-a": ["clm-c", "clm-b", "clm-d", "clm-e"],
        "clm-b": ["clm-d", "clm-e", "clm-a", "clm-c"],
        "clm-c": ["clm-a", "clm-b", "clm-d", "clm-e"],
        "clm-d": ["clm-b", "clm-e", "clm-a", "clm-c"],
        "clm-e": ["clm-b", "clm-d", "clm-a", "clm-c"],
    }


def test_the_shortlist_is_the_first_k_of_the_ranking():
    assert shortlist.top_k(ranked(PAPER), k=2) == {
        "clm-a": ["clm-c", "clm-b"],
        "clm-b": ["clm-d", "clm-e"],
        "clm-c": ["clm-a", "clm-b"],
        "clm-d": ["clm-b", "clm-e"],
        "clm-e": ["clm-b", "clm-d"],
    }


def test_a_k_larger_than_the_pool_takes_the_whole_pool():
    assert shortlist.top_k(ranked(PAPER), k=50)["clm-a"] == ["clm-c", "clm-b", "clm-d", "clm-e"]


def test_equal_similarity_goes_to_the_lower_target_id():
    statements = {"clm-s": "monotone escape", "clm-y": "monotone escape", "clm-x": "monotone escape"}
    assert ranked(statements)["clm-s"] == ["clm-x", "clm-y"]


def test_a_pair_already_a_candidate_either_way_round_leaves_both_pools():
    shortlisted = ranked(PAPER, candidate_pairs=[("clm-c", "clm-a")])
    assert shortlisted["clm-a"] == ["clm-b", "clm-d", "clm-e"]
    assert shortlisted["clm-c"] == ["clm-b", "clm-d", "clm-e"]
    assert shortlisted["clm-b"] == ranked(PAPER)["clm-b"]


def test_a_shared_maths_symbol_outranks_the_lower_id():
    """Every statement folds to the word ``lambda``; only clm-z also carries clm-a's symbol."""
    statements = {
        "clm-a": "The rate $`\\lambda_c`$ is small.",
        "clm-b": "A bound on $`\\lambda_d`$.",
        "clm-z": "A bound on $`\\lambda_c`$.",
    }
    assert ranked(statements)["clm-a"] == ["clm-z", "clm-b"]


def test_a_display_fence_symbol_meets_the_same_symbol_written_inline():
    """``\\Gamma_{k}`` in a fence and ``\\Gamma_k`` inline are one symbol."""
    statements = {
        "clm-f": "It holds that\n\n``` math\n\\Gamma_{k} \\le 1\n```\n",
        "clm-g": "Growth of $`\\Gamma_j`$.",
        "clm-y": "Growth of $`\\Gamma_k`$.",
    }
    assert ranked(statements)["clm-f"] == ["clm-y", "clm-g"]
