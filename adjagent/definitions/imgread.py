"""imgread: the command that reads the clipboard image pasted into the project scratch directory."""

from adjagent import text as t
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="imgread",
        kind=Kind.COMMAND,
        body=f"""read image file `{t.PROJECT_TEMP_DIR}/clipboard-pasted.png`""",
    ),
)
