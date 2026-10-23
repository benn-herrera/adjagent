"""imgread: the command that reads the clipboard image pasted into the project scratch directory."""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="imgread",
        kind=Kind.COMMAND,
        body=f"""<!-- for use with shell commands that save the image clipboard to a file to work around broken TUI image pasting. -->
read image file `{clauses.PROJECT_TEMP_DIR}/clipboard-pasted.png`""",
    ),
)
