#!/usr/bin/env bash
# `sweep-python`'s body. The duplication sweep. One idea in two places is invisible inside either
# of them — nothing in a file reports a fact about two files — so it has been found here by
# adversarial multi-model review or by accident, and both are too expensive to be the standing
# instrument. This is the standing instrument.
#
# It EMITS CANDIDATES AND NEVER VERDICTS, and exits zero with findings on purpose: whether two sites
# are one idea is a judgment, and a gate here would be claiming it. Read the output, or hand it to a
# seat that will.
#
# Stdlib only under the system python3, like every other tool here, with PYTHONPATH at the
# repository root, the one import path every recipe uses. `--rev` sweeps a past tree.
#
# The prose half is `tests/test_adjagent.py::test_a_paragraph_two_outputs_carry_has_one_source`,
# which runs in `just test`: shared prose is one constant by construction.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"

PYTHONPATH="${PROJECT_ROOT}" python3 -m devtools.dupe_sweep python "$@"
