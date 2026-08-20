# Select the legacy GLES renderer before Ren'Py initializes the display.
# The prebuilt RenPy-Vita runtime targets the Vita's OpenGL ES 2 implementation.

init -1000 python:
    import os
    os.environ["RENPY_RENDERER"] = "gles"
