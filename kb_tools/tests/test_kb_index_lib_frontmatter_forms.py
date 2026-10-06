"""`kb_index_lib`'s frontmatter readers over the 1.0.0 golden documents (`fixtures/format-1.0.0/`)."""

from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_yaml

_NEW_ROOT = Path(__file__).parent / "fixtures" / "format-1.0.0" / "1.0.0" / "kb-root"


def test_the_two_node_leaf_reads_to_its_nodes_and_pairs() -> None:
    leaf = _NEW_ROOT / "b" / "c.md"

    experiments = kb_index_lib.parse_experiment_leaf(leaf, _NEW_ROOT)
    supports = kb_index_lib.parse_support_leaf(leaf, _NEW_ROOT)

    assert [(node.id, node.status, node.strengthens) for node in experiments] == [
        ("exp-k3m9q2", "run", (("clm-0dtsyu", 0.8),)),
        ("exp-p4n8r1", "pending", ()),
    ]
    assert [(node.id, node.supports) for node in supports] == [
        ("sup-7x1a0c", (("clm-0dtsyu", 0.5), ("clm-2h6i01", kb_index_lib.PENDING_FRACTION))),
        ("sup-w2v6t5", ()),
    ]
    record = kb_index_lib.parse_leaf(leaf, _NEW_ROOT)
    assert record is not None and record.claims == ("clm-0dtsyu",)


def test_the_authored_id_inventory_reads_the_node_lists() -> None:
    inventory = kb_index_lib.scan_authored_ids(_NEW_ROOT)

    assert {node_id: record.hosting_leaf for node_id, record in inventory.items()} == {
        "clm-0dtsyu": "b/c.md",
        "exp-k3m9q2": "b/c.md",
        "exp-p4n8r1": "b/c.md",
        "sup-7x1a0c": "b/c.md",
        "sup-w2v6t5": "b/c.md",
    }


def test_a_yaml_document_is_stripped_to_its_body_up_link_first() -> None:
    text = (_NEW_ROOT / "a.md").read_text(encoding="utf-8")

    assert kb_index_lib.strip_frontmatter(text) == "[↑ KB](entry-point.md)\n\n\n# A\n"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[↑ Up](index.md)\n\n# Body\n", 0),
        ("---\nkind: leaf\nclaims: []\n---\n[↑ Up](index.md)\n\n# Body\n", 4),
        ("---\r\nkind: leaf\r\n---\r\n[↑ Up](index.md)\r\n", 3),
        ("---\nkind: entry-point\n---\n\n# KB\n", 3),
        ("---\nkind: leaf\n---\n", None),
        ("# Body\n\n---\nkind: leaf\n---\n", 0),
    ],
)
def test_the_up_link_stands_on_the_first_line_after_the_block_and_on_line_0_otherwise(
    text: str, expected: int | None
) -> None:
    assert kb_index_lib.uplink_index(text) == expected


def test_a_yaml_refusal_names_the_document_line() -> None:
    with pytest.raises(kb_yaml.KbYamlError) as refusal:
        kb_index_lib.parse_frontmatter("---\nkind: leaf\nclaims: &a [clm-aaaaaa]\n---\n")

    assert refusal.value.line == 3


@pytest.mark.parametrize(
    ("block", "reader", "error"),
    [
        ("experiment-nodes: exp-aaaaaa", kb_index_lib.parse_experiment_leaf, kb_index_lib.ExperimentLeafError),
        (
            "experiment-nodes:\n  - exp-id: exp-aaaaaa\n    status: run\n    strengthens:\n      - clm-bbbbbb: high",
            kb_index_lib.parse_experiment_leaf,
            kb_index_lib.ExperimentLeafError,
        ),
        (
            "experiment-nodes:\n  - exp-id: exp-aaaaaa\n    status: run\n"
            '    strengthens:\n      - clm-bbbbbb: "*pending*"',
            kb_index_lib.parse_experiment_leaf,
            kb_index_lib.ExperimentLeafError,
        ),
        (
            "experiment-nodes:\n  - exp-id: exp-aaaaaa\n    status: run\n    strengthens:\n      - clm-bbbbbb: 1.5",
            kb_index_lib.parse_experiment_leaf,
            kb_index_lib.ExperimentLeafError,
        ),
        (
            "experiment-nodes:\n  - exp-id: exp-aaaaaa\n    status: done",
            kb_index_lib.parse_experiment_leaf,
            kb_index_lib.ExperimentLeafError,
        ),
        (
            "support-nodes:\n  - sup-id: sup-aaaaaa\n    supports:\n      - clm-bbbbbb: true",
            kb_index_lib.parse_support_leaf,
            kb_index_lib.SupportLeafError,
        ),
        (
            "support-nodes:\n  - sup-id: sup-aaaaaa\n    supports:\n      - not-an-id: 0.5",
            kb_index_lib.parse_support_leaf,
            kb_index_lib.SupportLeafError,
        ),
        ("support-nodes:\n  - sup-id: exp-aaaaaa", kb_index_lib.parse_support_leaf, kb_index_lib.SupportLeafError),
    ],
)
def test_a_malformed_yaml_node_declaration_is_refused(tmp_path: Path, block: str, reader, error) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text(f"---\nkind: leaf\n{block}\n---\n[↑ Up](index.md)\n\n# Leaf\n", encoding="utf-8")

    with pytest.raises(error):
        reader(leaf, tmp_path)


def test_a_yaml_node_list_outside_a_leaf_declares_no_node(tmp_path: Path) -> None:
    index = tmp_path / "index.md"
    index.write_text("---\nkind: index\nexperiment-nodes: not-a-list\n---\n\n# Index\n", encoding="utf-8")

    assert kb_index_lib.parse_experiment_leaf(index, tmp_path) == []
