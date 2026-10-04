"""The two readings of a claim's printed name around a reference.

**The word before an anchor filters candidates.** An anchor the page introduces
with *Section*, *Figure* or a name classified as stating no result opens no
candidate pair where a fallback route chose the target, and removes nothing
containment settled. The fixture is read twice with only that word changed, so
what moves is what the word moved.

**A claim named by hand is a candidate.** A printed name and number with no
``\\ref`` joins a claim whose display line prints it, or a claim titled with
it, and nothing else. It is merged with whatever a reference reached on the same
pair and classed like every other candidate.

The authored graph is stood up from the inventory's own blocks rather than from
a declared pass: the narrowing reads ids, titles and locators, and joining a
block to its claim by locator is exactly what ``graph.read`` does.
"""

import pytest

from kb_tools.kb_claimgraph import attribute, graph, hand_named, inventory, tree
from kb_tools.kb_write import render

_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_UPLINK = "[↑ Vol](index.md)"


def _anchor(target: str, shown: str) -> str:
    path, _, fragment = target.partition("#")
    return f'<a href="{target}" data-reference-type="ref" data-reference="sec:{fragment}">{shown}</a>'


def _leaves(*, open_word: str, proof_word: str) -> dict[str, str]:
    """Five leaves. ``open_word`` precedes a reference containment leaves open; ``proof_word`` one it settles."""
    return {
        "alpha.md": f"""{_UPLINK}

# Alpha

> <span id="thm:alpha">**Theorem**</span>
>
> **Theorem 1** (Alpha result). *Alpha follows from Lemma 2, from
> Lemmas 4 and 7, and from the bound of {open_word} {_anchor("gamma.md#gamma", "3")}. It is
> not Theorem 3 of <span class="citation" data-cites="x">(X 2020)</span>, nor
> <span class="citation" data-cites="x">(X 2020, Theorem 3)</span>.*

> **proof**
>
> *Proof.* As in {proof_word} {_anchor("delta.md#delta", "4")}. ◻
""",
        "beta.md": f"""{_UPLINK}

# Beta

> <span id="lem:beta">**Lemma**</span>
>
> **Lemma 2** (Beta lemma). *Beta holds.*
""",
        "gamma.md": f"""{_UPLINK}

# Gamma

> <span id="thm:g3">**Theorem**</span>
>
> **Theorem 3** (Gamma theorem). *Gamma holds.*

> <span id="lem:g4">**Lemma**</span>
>
> **Lemma 4** (Gamma lemma). *Gamma holds again.*
""",
        "delta.md": f"""{_UPLINK}

# Delta

> <span id="prop:delta">**Proposition**</span>
>
> **Proposition 5** (Delta result). *Delta is read beside {_anchor("gamma.md#gamma", "3")}.*
""",
        # A second block printing Proposition 5: a display line read as a
        # mention would join Delta's to this one.
        "epsilon.md": f"""{_UPLINK}

# Epsilon

> <span id="prop:twin">**Proposition**</span>
>
> **Proposition 5** (Twin result). *The twin holds.*
""",
    }


def _read(tmp_path, **words: str):
    root = tmp_path / "kb-root"
    leaves = _leaves(**words)
    index = "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n" + "".join(f"- [{name}]({name})\n" for name in leaves)
    files = {"entry-point.md": _ENTRY_POINT, "vol/index.md": index, **{f"vol/{n}": t for n, t in leaves.items()}}
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    documents = tree.read(root)
    sites = inventory.scan(documents)
    nodes = {}
    for block in sites.claim_blocks():
        printed = inventory.PRINTED_NAME_RE.match(block.display).group(1)
        claim_id = f"clm-{printed.lower().replace(' ', '')}-{block.document[4]}"
        nodes[claim_id] = graph.ClaimNode(
            id=claim_id, document=block.document, title=block.title, locator=block.display, identifier=block.identifier
        )
    return documents, sites, graph.AuthoredGraph(nodes=nodes)


def _narrow(tmp_path, *, open_word: str = "by", proof_word: str = "by") -> attribute.Attribution:
    documents, sites, authored = _read(tmp_path, open_word=open_word, proof_word=proof_word)
    return attribute.narrow(documents, authored, sites)


def _pairs(narrowed: attribute.Attribution, harvest: attribute.Harvest | None = None) -> set[tuple[str, str]]:
    """Every candidate pair, or those ``harvest`` reached."""
    return {c.pair for c in narrowed.candidates if harvest is None or harvest in c.harvests}


_T1, _L2, _T3, _L4, _P5, _TWIN = (
    "clm-theorem1-a",
    "clm-lemma2-b",
    "clm-theorem3-g",
    "clm-lemma4-g",
    "clm-proposition5-d",
    "clm-proposition5-e",
)


# --- the word before an anchor ---------------------------------------------


@pytest.mark.parametrize(
    "before, word",
    [
        ("(Theorem ", "Theorem"),
        ("by ", "by"),
        ("in Fig. ", "Fig."),
        ("see §", "§"),
        ("from Section\n", "Section"),
        ("[Lemma ", "Lemma"),
    ],
)
def test_the_word_before_an_anchor_is_read_as_the_page_shows_it(tmp_path, before, word):
    documents = _write_one(tmp_path, f"Text {before}{_anchor('leaf.md#leaf', '1')}.")
    (anchor,) = inventory.scan(documents).anchors
    assert anchor.preceding_word == word


@pytest.mark.parametrize(
    "between",
    [" and ", ", ", ", and ", "–", " or ", ",\nand "],
)
def test_an_anchor_continuing_a_printed_list_carries_the_word_the_list_opened_with(tmp_path, between):
    documents = _write_one(
        tmp_path, f"Sections {_anchor('leaf.md#leaf', '4')}{between}{_anchor('leaf.md#leaf', '5')} hold."
    )
    assert [anchor.preceding_word for anchor in inventory.scan(documents).anchors] == ["Sections", "Sections"]


def test_an_anchor_after_prose_takes_its_own_word_rather_than_the_previous_anchor_s(tmp_path):
    documents = _write_one(
        tmp_path, f"Section {_anchor('leaf.md#leaf', '4')} is proved by {_anchor('leaf.md#leaf', '5')}."
    )
    assert [anchor.preceding_word for anchor in inventory.scan(documents).anchors] == ["Section", "by"]


def _write_one(tmp_path, body: str) -> tree.Tree:
    root = tmp_path / "kb-root"
    for path, text in {
        "entry-point.md": _ENTRY_POINT,
        "vol/index.md": "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n- [Leaf](leaf.md)\n",
        "vol/leaf.md": f"{_UPLINK}\n\n# Leaf\n\n{body}\n",
    }.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tree.read(root)


@pytest.mark.parametrize(
    "word, names_none",
    [
        ("Section", True),
        ("sections", True),
        ("Sec.", True),
        ("§", True),
        ("Fig.", True),
        ("Figures", True),
        ("Table", True),
        ("Appendix", True),
        ("Subsection", True),
        ("Remark", True),
        ("Assumptions", True),
        ("Definition", True),
        ("Theorem", False),
        ("Lemmas", False),
        ("Proposition", False),
        ("Equation", False),
        ("Eq.", False),
        ("by", False),
        ("in", False),
        ("Hypothesis", False),
        ("Proof", False),
        (None, False),
    ],
)
def test_which_words_name_a_kind_no_premise_relation_can_hold(word, names_none):
    assert attribute.names_no_premise(word) is names_none


def test_a_reference_the_page_calls_a_section_opens_no_candidate(tmp_path):
    """Theorem 1 points at Section 3, which hosts two claims; Proposition 5 points at it with *by*."""
    plain, filtered = _narrow(tmp_path / "a"), _narrow(tmp_path / "b", open_word="Section")
    referenced = attribute.Harvest.REFERENCE

    assert {(_T1, _T3), (_T1, _L4), (_P5, _T3), (_P5, _L4)} <= _pairs(plain, referenced)
    assert _pairs(plain, referenced) - _pairs(filtered, referenced) == {(_T1, _T3), (_T1, _L4)}
    # Theorem 1's body also names Lemma 4 by hand, so that pair is a candidate
    # anyway and was never only the word's to drop.
    assert set(filtered.word_dropped) == {(_T1, _T3)}
    assert (_T1, _T3) not in _pairs(filtered)
    assert plain.word_dropped == ()


@pytest.mark.parametrize("proof_word", ["Section", "by", "Figure"])
def test_the_word_never_moves_an_edge_containment_settled(tmp_path, proof_word):
    """The proof of Theorem 1 points at a single-claim document: settled whatever the page calls it."""
    narrowed = _narrow(tmp_path, open_word="Section", proof_word=proof_word)
    assert narrowed.edges == ((_T1, _P5),)


# --- a claim named by hand -------------------------------------------------


def test_a_claim_named_by_hand_in_a_claim_body_is_a_candidate(tmp_path):
    """*Lemma 2* joins Beta; *Lemmas 4 and 7* joins Lemma 4 and nothing for 7; cited theorems join nothing."""
    documents, sites, authored = _read(tmp_path, open_word="Section", proof_word="by")
    found = {(c.source, c.target): c.mention for c in hand_named.harvest(documents, authored, sites)}
    assert found == {(_T1, _L2): "Lemma 2", (_T1, _L4): "Lemmas 4 and 7"}

    # Classed and drafted like any other: a claim-to-claim pair, offered all
    # three letters, drafted *mention*, its passage the mention's paragraph.
    narrowed = attribute.narrow(documents, authored, sites)
    named = {c.pair: c for c in narrowed.candidates if attribute.Harvest.HAND_NAMED in c.harvests}
    assert set(named) == set(found)
    for candidate in named.values():
        assert candidate.harvests == {attribute.Harvest.HAND_NAMED}
        assert candidate.offered == tuple(attribute.Relation)
        assert candidate.draft is attribute.Relation.MENTION
        assert len(candidate.passages) == 1 and "Lemma 2" in candidate.passages[0]
    assert set(found) <= set(narrowed.references)


def test_a_hand_named_pair_a_reference_already_reached_is_one_candidate(tmp_path):
    """With *by* before it, the Section 3 anchor opens Theorem 1 → Lemma 4 itself, and the two merge."""
    narrowed = _narrow(tmp_path)
    (merged,) = [c for c in narrowed.candidates if c.pair == (_T1, _L4)]
    assert merged.harvests == {attribute.Harvest.REFERENCE, attribute.Harvest.HAND_NAMED}
    assert _pairs(narrowed, attribute.Harvest.HAND_NAMED) == {(_T1, _L2), (_T1, _L4)}


def test_a_block_s_own_display_line_is_not_a_mention_of_its_twin(tmp_path):
    narrowed = _narrow(tmp_path)
    assert not {(_P5, _TWIN), (_TWIN, _P5)} & _pairs(narrowed)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("follows directly from Lemma 4.6", [("lemma", ("4.6",))]),
        ("This proves Theorem B.", [("theorem", ("B",))]),
        ("by Lemma 4.6a", [("lemma", ("4.6",))]),
        ("Theorem 2.4.1 holds", [("theorem", ("2.4.1",))]),
        ("by Lemmas 2 and 3", [("lemma", ("2", "3"))]),
        ("Theorems 1, 2, and 4", [("theorem", ("1", "2", "4"))]),
        ("Corollaries 1–2", [("corollary", ("1", "2"))]),
        ("by lemma 5", [("lemma", ("5",))]),
        ("Main Theorem 1 and Theorem 2", [("main theorem", ("1",)), ("theorem", ("2",))]),
        ("a sublemma 3", []),
        ("Theorem Bounds", []),
        ("Remark 3", []),
        ("the Theorem of Pythagoras", []),
        ('(X 2020, <span class="citation" data-cites="x">Theorem 3</span>)', []),
        ('Theorem 3 of <span class="citation" data-cites="x">(X 2020)</span>', []),
        ('Lemma 5 in\n<span class="citation" data-cites="x">(X 2020)</span>', []),
        ('Lemma <a href="b.md#l" data-reference-type="ref" data-reference="l">2</a>', []),
    ],
)
def test_what_a_hand_written_mention_reads(text, expected):
    vocabulary = hand_named.Vocabulary(frozenset({"Theorem", "Lemma", "Corollary", "Main Theorem"}))
    assert [(name, numbers) for _, name, numbers, _ in vocabulary.mentions(text)] == expected


def test_the_names_are_the_corpus_s_own():
    vocabulary = hand_named.Vocabulary(frozenset({"Result"}))
    assert [(name, numbers) for _, name, numbers, _ in vocabulary.mentions("by Result 2 and Theorem 2")] == [
        ("result", ("2",))
    ]


@pytest.mark.parametrize(
    "title, label",
    [
        ("Theorem 9", ("theorem", "9")),
        ("Theorem 9.", ("theorem", "9")),
        ("Theorem 9 (Main bound)", ("theorem", "9")),
        ("Lemma A.2", ("lemma", "A.2")),
        ("Lemma 2 implies the bound", None),
        ("The bound of Theorem 9", None),
    ],
)
def test_a_title_joins_only_where_it_is_the_label_whole(title, label):
    assert hand_named.Vocabulary(frozenset({"Theorem", "Lemma"})).label(title) == label


def test_a_prose_claim_titled_with_a_label_is_joined_and_its_paragraph_is_scanned(tmp_path):
    """A claim with no block joins by title, and its own paragraph is a body the harvest reads."""
    documents, sites, authored = _read(tmp_path, open_word="by", proof_word="by")
    marker = render.render_tier2_marker("clm-prose")
    leaf = tmp_path / "kb-root" / "vol" / "beta.md"
    leaf.write_text(
        leaf.read_text(encoding="utf-8") + f"\nThe prose result rests on Theorem 3 and Theorem 9. {marker}\n",
        encoding="utf-8",
    )
    documents = tree.read(tmp_path / "kb-root")
    sites = inventory.scan(documents)
    nodes = dict(authored.nodes)
    nodes["clm-prose"] = graph.ClaimNode(
        id="clm-prose", document="vol/beta.md", title="Theorem 9", locator=None, identifier=None
    )
    found = {(c.source, c.target) for c in hand_named.harvest(documents, graph.AuthoredGraph(nodes=nodes), sites)}

    assert (_T1, _L2) in found
    # Theorem 3 joins Gamma's block; Theorem 9 is the prose claim itself, and a claim never names itself.
    assert ("clm-prose", _T3) in found
    assert ("clm-prose", "clm-prose") not in found
