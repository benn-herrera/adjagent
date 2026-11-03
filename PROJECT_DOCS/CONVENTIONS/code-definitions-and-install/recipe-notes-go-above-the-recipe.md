### Recipe notes go above the recipe

A `just` recipe's note goes above the recipe, not in its body. A body with no shebang is run
line by line, and `just` echoes every line it runs, `#` included: a note there prints on every
invocation, so a note explaining the recipe reads as its output. Above the recipe the line is
never a command line and stays silent under either body.
