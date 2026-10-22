init python:
    import time

    renpy.music.register_channel("music1","music")
    renpy.music.register_channel("music2","music")
    renpy.music.register_channel("music3","music")
    renpy.music.register_channel("loop_se","sfx")

    bgi_char_pos = [0] * 31
    bgi_f30x_pos = [0] * 31

    if persistent.global_var is None:
        persistent.global_var = [0] * 256

    bgi_f14b_dict = {}
    bgi_base_var = {}

    bgi_choices = []
    bgi_nvl_mode = 0
    bgi_timer = 0

    # Saves and rollback only record store names assigned after init. The
    # BGI slot tables and variables are only ever mutated in place, so the
    # original game never saved them: a load resumed with whatever tables
    # the session last built, or with empty slots after a fresh boot
    # (bgi_f_2c6 then failed on 0["name"]). These callbacks give them
    # `default` semantics without adding script statements, which would
    # shift the global node serials that existing saves depend on.
    BGI_SAVED_STATE = ("bgi_char_pos", "bgi_f30x_pos", "bgi_base_var")

    # Parameter names of the ATL transforms that bgi_f_2c0/2c2/2c4/2c6/2c8
    # and bgi_f_236 show slot sprites with, mapped to the parameters that
    # hold the slot's x2, y2 and angle.
    BGI_CHAR_TRANSFORMS = {
        frozenset(("x2", "y2")): ("x2", "y2", None),
        frozenset(("t", "x1", "x2", "y1", "y2", "r")): ("x2", "y2", "r"),
        frozenset(("t", "x2", "y2", "r1", "r2")): ("x2", "y2", "r2"),
        frozenset(("t", "x2", "y2")): ("x2", "y2", None),
        frozenset(("t", "x", "y", "dx", "dy", "cnt")): ("x", "y", None),
    }

    def bgi_new_state(name):
        if name == "bgi_base_var":
            return {}
        return [0] * 31

    def bgi_shown_image_name(d):
        """
        Returns the name of the image a scene list entry shows, or None.
        renpy.show(tag=...) replaces the entry's own name with the tag, so
        the name comes from the ImageReference under the slot's transform.
        """

        while d is not None and not isinstance(d, renpy.display.image.ImageReference):
            d = getattr(d, "child", None)

        if d is None:
            return None

        return " ".join(d.name)

    def bgi_shown_slots(layer):
        """
        Yields (slot, scene list entry, image name, ATL parameters) for every
        numbered slot tag shown on `layer`.
        """

        for e in renpy.game.context().scene_lists.layers.get(layer, ()):
            if e.tag is None or not e.tag.isdigit():
                continue

            slot = int(e.tag)
            name = bgi_shown_image_name(e.displayable)
            params = getattr(getattr(e.displayable, "context", None), "context", None)

            # ATL contexts are plain dicts; the store's dict is RevertableDict.
            if slot < 31 and name is not None and isinstance(params, python_dict):
                yield slot, e, name, params

    def bgi_rebuild_slots():
        """
        Rebuilds the slot tables of a save made before they were saved,
        from the sprites the save shows. Anchor offsets are not recoverable
        (they are 0 in 1776 of the 1795 bgi_f_2c0 calls), and f30x slots
        whose image was never shown stay empty.
        """

        for slot, e, name, params in bgi_shown_slots("master"):
            keys = BGI_CHAR_TRANSFORMS.get(frozenset(params))

            if keys is None or bgi_char_pos[slot] != 0:
                continue

            x2, y2, angle = keys
            bgi_char_pos[slot] = {
                "name": name,
                "x2": params[x2],
                "y2": params[y2],
                "xa": 0,
                "ya": 0,
                "z": e.zorder,
                "angle": params[angle] if angle else 0,
                "trig": 1,
                "tag": e.tag,
            }

        for slot, e, name, params in bgi_shown_slots("f30x"):
            if bgi_f30x_pos[slot] != 0:
                continue

            bgi_f30x_pos[slot] = {
                "name": name,
                "xanchor": params.get("xa", 0.0),
                "yanchor": params.get("ya", 0.0),
                "x2": params.get("x2", 0),
                "y2": params.get("y2", 0),
                "z": e.zorder,
                "angle": 0,
                "alpha": params.get("a", 1.0),
                "trig": 0,
            }

    def bgi_track_state(start):
        d = store.__dict__
        missing = [ n for n in BGI_SAVED_STATE if start or n not in d.ever_been_changed ]

        for n in missing:
            d[n] = bgi_new_state(n)
            d.ever_been_changed.add(n)

        if missing and not start:
            bgi_rebuild_slots()

    def bgi_start_state():
        bgi_track_state(True)

    def bgi_after_load_state():
        bgi_track_state(False)

    config.start_callbacks.append(bgi_start_state)
    config.after_load_callbacks.append(bgi_after_load_state)

    def bgi_push_dword(num):
        bgi_stack.append(num)

    def bgi_push_offset(num):
        bgi_stack.append(num)

    def bgi_push_base_offset(num):
        bgi_stack.append(bgi_stack_base - num)

    def bgi_push_string(str):
        bgi_stack.append(str)

    def bgi_load(num):
        p1 = bgi_stack.pop()
        if p1 not in bgi_base_var.keys():
            bgi_base_var[p1] = 0
        bgi_stack.append(bgi_base_var[p1])

    def bgi_move(num):
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_base_var[p2] = p1

    def bgi_move_arg(num):
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_base_var[p1] = p2

    def bgi_load_base():
        bgi_stack.append(bgi_stack_base)

    def bgi_store_base():
        global bgi_stack_base
        bgi_stack_base = bgi_stack.pop()

    def bgi_jmp():
        p1 = bgi_stack.pop()
        renpy.jump(p1)

    def bgi_jc(num):
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        if p2 == 0:
            renpy.jump(p1)

    def bgi_reg_exception_handler():
        p1 = bgi_stack.pop()

    def bgi_unreg_exception_handler():
        pass

    def bgi_add():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p1 + p2)

    def bgi_sub():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 - p1)

    def bgi_mul():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 * p1)

    def bgi_div():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 / p1)

    def bgi_sar():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 >> (p1&0x1f))

    def bgi_eq():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 == p1)

    def bgi_neq():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 != p1)

    def bgi_leq():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 <= p1)

    def bgi_geq():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 >= p1)

    def bgi_lt():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 < p1)

    def bgi_gt():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 > p1)

    def bgi_bool_and():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 and p1)

    def bgi_bool_or():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_stack.append(p2 or p1)

    def bgi_bool_zero():
        p1 = bgi_stack.pop()
        bgi_stack.append(p1 == 0)

    def bgi_line(file,line):
        pass

    def bgi_f_0e0():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_local_var[p1] = p2

    def bgi_f_0e1():
        p1 = bgi_stack.pop()
        bgi_stack.append(bgi_local_var[p1])

    def bgi_f_0e2():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_local_var[p1] = p2

    def bgi_f_0e3():
        p1 = bgi_stack.pop()
        bgi_stack.append(bgi_local_var[p1])

    def bgi_f_0e4():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        bgi_local_var1[p1] = p2

    def bgi_f_0e5():
        p1 = bgi_stack.pop()
        bgi_stack.append(bgi_local_var1[p1])

    def bgi_f_0e6():
        p1 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        persistent.global_var[p1] = p2

    def bgi_f_0e7():
        p1 = bgi_stack.pop()
        bgi_stack.append(persistent.global_var[p1])

    def bgi_f_0f0():
        _window_hide(trans=0, auto=False)
        p1 = bgi_stack.pop()
        p1 = p1.lower()
        p1 = p1.replace('-', '_')
        renpy.call('l' + p1)

    def bgi_f_101():
        bgi_stack.append(int(time.time() * 1000))

    def bgi_f_12c():
        bgi_stack.append(0)

    def bgi_renpy_text_refine(text):
        text = text.replace('%', '%%')
        text = text.replace('{', '{{')
        text = text.replace('[', '[[')
        return text

    def bgi_renpy_text_f14b(text):
        for key,value in bgi_f14b_dict.items():
            text = text.replace(key, "{rb}%s{/rb}{rt}%s{/rt}" %(key,value))
        bgi_f14b_dict.clear()
        return text

    def bgi_f_140():
        bgi_clean_cache()

        p5 = bgi_stack.pop()
        p4 = bgi_stack.pop()
        p3 = bgi_stack.pop()
        p2 = bgi_stack.pop()
        p1 = bgi_stack.pop()

        p5 = bgi_renpy_text_f14b(bgi_renpy_text_refine(p5))

        if bgi_nvl_mode == 0:
            if p4 != 0:
                renpy.say(p4,p5)
            else:
                renpy.say(None,p5)
        else:

            p5 = '{cps=%d}%s{/cps}' %(bgi_text_cps,p5)
            if p2 == 0:
                p5 = p5 + '{nw}'

            if p4 != 0:
                renpy.say(nvl_narrator,"{color=#00314fff}{size=+6}%s{/size}{/color} %s" %(p4,p5))
            else:
                renpy.say(nvl_narrator,"%s" % p5)




    def bgi_f_164():
        bgi_choices.clear()

    def bgi_f_168():
        global bgi_choices
        x = 0
        y = 0
        pic = ''
        txt = ''

        p2 = bgi_stack.pop()
        p1 = bgi_stack.pop()

        for c in range(p2):
            pic = bgi_base_var[p1 + 16*c + 0]
            x = bgi_base_var[p1 + 16*c + 4]
            y = bgi_base_var[p1 + 16*c + 8]
            txt = bgi_base_var[p1 + 16*c + 12]
            bgi_choices.append((txt,c))
        user_choice = renpy.display_menu(bgi_choices)
        bgi_stack.append(user_choice)
        bgi_choices.clear()

    def bgi_f_169():
        renpy.show('sgscslct990000',tag='30',zorder=0)
        renpy.music.play('audio/bgm019.ogg', channel="music", fadein=1.0,relative_volume=1.0)

        bgi_choices.clear()
        bgi_choices.append(("Down the Rabbit-Hole II",0))

        if persistent.global_var[231]:
            bgi_choices.append(("It\'s my own Invention",1))
        if persistent.global_var[232]:
            bgi_choices.append(("Looking-glass Insects",2))
        if persistent.global_var[233]:
            bgi_choices.append(("Jabberwocky",3))
        if persistent.global_var[234]:
            bgi_choices.append(("Which Dreamed It",4))
        if persistent.global_var[235]:
            bgi_choices.append(("Jabberwocky II",5))
        if persistent.global_var[236]:
            bgi_choices.append(("The Hill of Sunflowers",6))
        if persistent.global_var[237]:
            bgi_choices.append(("Wonderful Everyday",7))
        if persistent.global_var[238]:
            bgi_choices.append(("End Sky II",8))

        user_choice = renpy.display_menu(bgi_choices)
        renpy.music.stop(channel="music",fadeout=1.0)
        renpy.scene()
        renpy.scene(layer='f30x')
        renpy.show('black',tag='30',zorder=0)
        renpy.with_statement(Dissolve(p1/1000.0))
        bgi_stack.append(user_choice)

    def bgi_f_01c():
        global bgi_stack
        p1 = bgi_stack.pop()
        if p1 == 'RandomNumberReturn':
            bgi_stack.pop()
            bgi_stack.pop()
            bgi_stack.append(0)

        elif p1 == 'BSPosX' or p1 == 'BSPosY' or p1 == 'SPPosY' or p1 == 'SPPosX':
            bgi_stack.pop()
            bgi_stack.append(0)
        else:
            bgi_stack = []
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
