"""Shared sections: text more than one definition renders, each written once.

Each module holds one family of `Section` subclasses and exports nothing else.
A class's fields are what varies between the definitions that use it, with the
common case as default; facts that vary by language or platform arrive through a
`Profile` field. The paragraphs a class emits are private to its module, and a
value from the harness or the family reaches one only through the `Render` its
`render` receives.
"""
