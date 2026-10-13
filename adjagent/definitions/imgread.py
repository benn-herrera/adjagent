"""imgread: the command that reads the clipboard image pasted into the project scratch directory."""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="imgread",
        kind=Kind.COMMAND,
        body=f"""read image file `{clauses.PROJECT_TEMP_DIR}/clipboard-pasted.png`""",
    ),
)
