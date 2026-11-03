### Reference retakes follow acceptance

`just retake-reference` is run only after a content change is accepted. It overwrites the
baseline `just render-diff` compares against, so running it earlier erases the change from the
next comparison.

