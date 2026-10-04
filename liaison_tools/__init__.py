"""liaison_tools — transport/session helpers shared by the liaison agents.

The tools are invoked by command line, and each is hyphenated so that no tool
admits an import. One module does: ``openai_chat``, the chat-completions
request the transport command is built on, for a caller that wants it in-process.
This package marker also lets the test suite under ``tests/`` collect with a
stable module path alongside the ``kb_tools`` suite.
"""
