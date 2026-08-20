image black = "#000"
image white = "#fff"
image red = "#f00"

style ruby_style is default:
    size 12
    yoffset -20

style say_dialogue:
    line_leading 12
    ruby_style style.ruby_style

init:
    python:
        import math

        class Shaker(object):

            anchors = {
                'top' : 0.0,
                'center' : 0.5,
                'bottom' : 1.0,
                'left' : 0.0,
                'right' : 1.0,
                }

            def __init__(self, start, child, dist):
                if start is None:
                    start = child.get_placement()

                self.start = [ self.anchors.get(i, i) for i in start ]
                self.dist = dist
                self.child = child

            def __call__(self, t, sizes):


                def fti(x, r):
                    if x is None:
                        x = 0
                    if isinstance(x, float):
                        return int(x * r)
                    else:
                        return x

                xpos, ypos, xanchor, yanchor = [ fti(a, b) for a, b in zip(self.start, sizes) ]

                xpos = xpos - xanchor
                ypos = ypos - yanchor

                nx = xpos + (1.0-t) * self.dist * (renpy.random.random()*2-1)
                ny = ypos + (1.0-t) * self.dist * (renpy.random.random()*2-1)

                return (int(nx), int(ny), 0, 0)

        def _Shake(start, time, child=None, dist=100.0, **properties):

            move = Shaker(start, child, dist=dist)

            return renpy.display.layout.Motion(move,
                          time,
                          child,
                          add_sizes=True,
                          **properties)

        Shake = renpy.curry(_Shake)

init python:
    bgi_sakura = 0

label splashscreen:
    $ bgi_stack = []
    $ bgi_stack_base = 0
    $ bgi_push_string('makerlogo')
    $ bgi_f_0f0()
    return

label start:
    $ bgi_local_var = [0] * 256
    $ bgi_local_var1 = [0] * 256

    $ bgi_stack = []
    $ bgi_stack_base = 0

    $ bgi_font_size = 34
    $ bgi_text_cps = 0

    stop music fadeout 1.0
    scene black with Dissolve(1.0)


    $ bgi_push_string('main')


    $ bgi_f_0f0()
    return
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
