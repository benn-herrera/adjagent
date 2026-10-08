"""Shared sections: text more than one definition renders, each written once.

A section is a module constant when it takes nothing, and a function of keyword
arguments otherwise; variation is a parameter, and one section composing another
is a call. A section needing a harness value takes the `Render` as its first
positional parameter. Every section returns text with no leading or trailing
newline, and knows nothing about which definition calls it.
"""
