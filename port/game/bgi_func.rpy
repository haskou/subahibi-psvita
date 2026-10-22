









































































































init python:
    import math

    def bgi_clean_pic():
        for char in bgi_char_pos:
            if char != 0:
                if char["trig"] != 0:
                    renpy.hide(name = char["tag"])
    def bgi_clean_cache():
        for char in bgi_char_pos:
            if char != 0:
                char["trig"] = 1

    def bgi_cal_zoom(zi):
        return math.exp(zi/-1000.0)

    def bgi_make_music_channel(c):
        if c == 0:
            return u'music'
        elif c == 1:
            return u'music1'
        elif c == 2:
            return u'music2'
        elif c == 3:
            return u'music3'
        else:

            return u'music'


label bgi_f_0a0:
    $ p1 = bgi_stack.pop()
    $ bgi_stack.append(renpy.random.randint(0, p1))
    return

label bgi_f_0f4:
    $ MainMenu(confirm=False)()

label bgi_f_110:
    if bgi_nvl_mode == 0:
        $ p1 = bgi_stack.pop()
        $ renpy.pause(p1/1000.0)
    else:
        nvl show
        $ p1 = bgi_stack.pop()
        $ renpy.pause(p1/1000.0)
    return

label bgi_f_111:
    return

label bgi_f_112:
    $ p1 = bgi_stack.pop()
    $ bgi_timer = int(time.time() * 1000)
    return

label bgi_f_113:
    $ p1 = bgi_stack.pop()
    $ renpy.pause(p1/1000.0)
    return

label bgi_f_114:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_118:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_119:
    return

label bgi_f_11b:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_11c:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_120:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_121:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_122:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_123:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_124:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_125:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_141:
    $ nvl_clear()
    return

label bgi_f_142:
    if bgi_nvl_mode == 0:
        $ renpy.say(None,"\n{nw}")
    else:
        $ renpy.say(nvl_narrator,"\n{nw}")
    return

label bgi_f_143:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_144:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_145:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if p2 == 0:
        $ bgi_text_cps = 0
    else:
        $ bgi_text_cps = p1
    return

label bgi_f_146:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_147:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_14b:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_f14b_dict[p2] = p1
    return

label bgi_f_14c:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_font_size = p2
    return

label bgi_f_151:
    window hide
    return

label bgi_f_152:
    $ p1 = bgi_stack.pop()

    $ _window_show(trans=Dissolve(p1/1000.0), auto=False)
    return

label bgi_f_153:
    $ p1 = bgi_stack.pop()
    $ _window_hide(trans=Dissolve(p1/1000.0), auto=False)
    return

label bgi_f_158:
    $ p1 = bgi_stack.pop()
    if p1:
        $ _window_show(auto=False)
        $ bgi_nvl_mode = 1
    else:
        $ bgi_nvl_mode = 0
    return

label bgi_f_15e:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_16c:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_180:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_chan = bgi_make_music_channel(p4)
    $ renpy.music.play('audio/' + p3 + '.ogg', channel=bgi_chan, fadein=p1/1000.0,relative_volume=p2/128.0)

    return

label bgi_f_184:
    $ p1 = bgi_stack.pop()
    $ bgi_chan = bgi_make_music_channel(p1)
    $ renpy.pause(bgi_trans_time)
    $ renpy.music.stop(channel=bgi_chan)
    return

label bgi_f_185:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0

    $ bgi_chan = bgi_make_music_channel(p3)
    $ renpy.music.stop(channel=bgi_chan,fadeout=bgi_trans_time)
    if p1:
        $ renpy.pause(bgi_trans_time)
    return

label bgi_f_186:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_chan = bgi_make_music_channel(p3)
    $ renpy.music.set_volume(p2/128.0, delay=p1/1000.0, channel=bgi_chan)
    return

label bgi_f_190:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()




    $ renpy.music.play('audio/' + p3 + '.ogg', channel='loop_se', loop=True, fadein=p1/1000.0,relative_volume=p2/128.0)
    return

label bgi_f_194:
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel='loop_se')
    return

label bgi_f_195:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel='loop_se',fadeout=p2/1000.0)
    return

label bgi_f_196:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ renpy.music.set_volume(p2/128.0, delay=p1/1000.0, channel='loop_se')
    return

label bgi_f_198:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.music.play('audio/' + p3 + '.ogg', channel='loop_se', loop=None, fadein=p1/1000.0,relative_volume=p2/128.0)
    return

label bgi_f_19c:
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel='loop_se')
    return

label bgi_f_19d:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel='loop_se',fadeout=p2/1000.0)
    return

label bgi_f_19e:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_1a0:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.music.play('audio/' + p3 + '.ogg', channel=u'sound', relative_volume=p2/128.0)
    return

label bgi_f_1a1:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.music.play('audio/' + p2 + '.ogg', channel=u'sound', relative_volume=p1/128.0)
    return

label bgi_f_1a2:
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel=u'sound', fadeout=None)
    return

label bgi_f_1a3:
    $ p1 = bgi_stack.pop()
    $ renpy.pause(renpy.music.get_duration(channel=u'sound'))
    return

label bgi_f_1a4:
    if bgi_sakura != 1:
        $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.music.play('audio/' + p2 + '.ogg', channel=u'sound', relative_volume=p1/128.0)
    return

label bgi_f_1a5:
    $ p1 = bgi_stack.pop()
    $ voice('audio/' + p1 + '.ogg')
    return

label bgi_f_1a6:
    $ p1 = bgi_stack.pop()
    $ renpy.music.stop(channel=u'voice', fadeout=None)
    return

label bgi_f_1a7:
    $ p1 = bgi_stack.pop()
    $ renpy.pause(1.0)
    return

label bgi_f_1a8:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_1a9:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_1ac:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_1bf:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_230:
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_232:
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_233:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

transform bgitrans_f_236(t, x, y, dx, dy, cnt):
    xoffset x
    yoffset y
    parallel:
        linear t xoffset x + dx
    parallel:
        linear t yoffset y + dy

    xoffset x + dx
    yoffset y + dy

    parallel:
        linear t xoffset x
    parallel:
        linear t yoffset y

    repeat cnt

label bgi_f_236:
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_img = bgi_char_pos[p7]["name"]
    $ bgi_tag = str(p7)
    $ bgi_x2 = bgi_char_pos[p7]["x2"]
    $ bgi_y2 = bgi_char_pos[p7]["y2"]

    $ bgi_shake_time = 0.5*p5/p6
    $ bgi_shake_range = p5

    if p3 > 4:
        if p6 == 256:
            $ p3 = 1
        else:
            pass




    if p3 == 0:
        $ bgi_shake_dx = p5
        $ bgi_shake_dy = 0
    elif p3 == 1:
        $ bgi_shake_dx = -1 * int(p5/1.4)
        $ bgi_shake_dy = int(p5/1.4)
    elif p3 == 2:
        $ bgi_shake_dx = 0
        $ bgi_shake_dy = p5
    elif p3 == 3:
        $ bgi_shake_dx = int(p5/1.4)
        $ bgi_shake_dy = -1 * int(p5/1.4)
    elif p3 == 4:
        $ bgi_shake_dx = p5
        $ bgi_shake_dy = 0
    else:
        $ bgi_shake_dx = 0
        $ bgi_shake_dy = 0

    $ bgi_shake_cnt = 10000 if p2==0 else p2/2

    if p6 == 256:
        $ bgi_shake_cnt = 3
    if p6 == 1:
        $ bgi_shake_time = 1.0
    $ renpy.show(name=bgi_img,at_list=[bgitrans_f_236(bgi_shake_time,bgi_x2,bgi_y2,bgi_shake_dx,bgi_shake_dy,bgi_shake_cnt)],tag=bgi_tag,zorder=bgi_char_pos[p7]["z"])
    return

label bgi_f_237:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_238:
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_23c:
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_23d:
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_240:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_img = p3.lower()
    $ renpy.show(bgi_img,tag='30',zorder=0)
    if p1:
        $ renpy.with_statement(Dissolve(p2/1000.0))
    return

label bgi_f_241:
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_img = p5.lower()
    # Was the unused bgi_imdis store; kept as one statement for save names.
    pass
    $ renpy.show(bgi_img,tag='30',zorder=0)

    $ renpy.with_statement(Dissolve(p2/1000.0))
    return

label bgi_f_242:
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

transform bgitrans_f_248(t, x1, x2, y1, y2):
    yalign 0.5
    xalign 0.5

    parallel:
        xoffset x1
        linear t xoffset x2
    parallel:
        yoffset y1
        linear t yoffset y2


label bgi_f_248:
    $ p11 = bgi_stack.pop()
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_img = p11.lower()
    $ bgi_x1 = p10
    $ bgi_x2 = p7
    $ bgi_y1 = p9
    $ bgi_y2 = p6
    $ bgi_trans_time = p2/1000.0

    $ renpy.show(bgi_img,tag='30',at_list=[bgitrans_f_248(bgi_trans_time,bgi_x1,bgi_x2,bgi_y1,bgi_y2)],zorder=0)
    if p1:
        $ renpy.pause(bgi_trans_time)

    return

label bgi_f_24c:
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_280:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.scene(layer='f30x')
    $ bgi_clean_pic()
    $ bgi_clean_cache()

    $ bgi_img = p2.lower()
    $ renpy.show(bgi_img,tag='30')
    $ renpy.with_statement(Dissolve(p1/1000.0))
    return

label bgi_f_281:
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.scene(layer='f30x')
    $ bgi_clean_pic()
    $ bgi_clean_cache()

    $ bgi_img = p5.lower()
    # Was the unused bgi_imdis store; kept as one statement for save names.
    pass
    $ renpy.show(bgi_img,tag='30',zorder=0)
    $ renpy.with_statement(Dissolve(p1/1000.0))
    return

label bgi_f_284:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_288:
    $ p1 = bgi_stack.pop()
    $ renpy.scene()
    $ renpy.scene(layer='f30x')
    $ renpy.show('black',tag='30',zorder=0)
    $ renpy.with_statement(Dissolve(p1/1000.0))
    return

label bgi_f_289:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    # Was the unused bgi_imdis store; kept as one statement for save names.
    pass
    $ renpy.scene()
    $ renpy.scene(layer='f30x')
    $ renpy.show('black',tag='30')
    $ renpy.with_statement(Dissolve(p1/1000.0))
    return

transform bgitrans_f_2c0_1(t, x1, x2, y1, y2, r):
    rotate r
    rotate_pad False
    yalign 1.0
    xalign 0.5

    parallel:
        xoffset x1
        linear t xoffset x2
    parallel:
        yoffset y1
        linear t yoffset y2

transform bgitrans_pos(x2, y2):
    xalign 0.5
    yalign 1.0
    xoffset x2
    yoffset y2

label bgi_f_2c0:
    $ p16 = bgi_stack.pop()
    $ p15 = bgi_stack.pop()
    $ p14 = bgi_stack.pop()
    $ p13 = bgi_stack.pop()
    $ p12 = bgi_stack.pop()
    $ p11 = bgi_stack.pop()
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if bgi_sakura == 1:
        $ p0 = bgi_stack.pop()



    $ bgi_img = p15.lower()
    $ bgi_tag = str(p16)
    $ bgi_zorder = p3

    $ bgi_x1 = p10 - p7
    $ bgi_x2 = p14 - p7
    $ bgi_y1 = p9 - p6
    $ bgi_y2 = p13 - p6

    $ bgi_char_pos[p16] = {}
    $ bgi_char_pos[p16]["name"] = bgi_img
    $ bgi_char_pos[p16]["x2"] = bgi_x2
    $ bgi_char_pos[p16]["y2"] = bgi_y2
    $ bgi_char_pos[p16]["xa"] = p7
    $ bgi_char_pos[p16]["ya"] = p6
    $ bgi_char_pos[p16]["z"] = p3
    $ bgi_char_pos[p16]["angle"] = -1*p5
    $ bgi_char_pos[p16]["trig"] = p1
    $ bgi_char_pos[p16]["tag"] = str(p16)
    if p11:
        $ renpy.show(name=bgi_img,at_list=[bgitrans_f_2c0_1(p2/1000.0,bgi_x1,bgi_x2,bgi_y1,bgi_y2,-1.0*p5)],tag=bgi_tag,zorder=bgi_zorder)
    else:
        $ renpy.show(name=bgi_img,at_list=[bgitrans_pos(bgi_x2,bgi_y2)],tag=bgi_tag,zorder=bgi_zorder)

    if p1:
        $ renpy.with_statement(Dissolve(p2/1000.0))
    return

transform bgitrans_f_2c2(t, x2, y2, r1, r2):
    rotate_pad False
    parallel:
        linear t xoffset x2
    parallel:
        linear t yoffset y2
    parallel:
        rotate r1
        linear t rotate r2

label bgi_f_2c2:
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if bgi_sakura == 1:
        $ p0 = bgi_stack.pop()

    if bgi_char_pos[p8] == 0:
        return

    $ bgi_trans_time = p2/1000.0
    $ bgi_r2 = -1 * p3
    $ bgi_x2 = p6 - bgi_char_pos[p8]["xa"]
    $ bgi_y2 = p5 - bgi_char_pos[p8]["ya"]
    $ bgi_r1 = bgi_char_pos[p8]["angle"]
    $ bgi_tag = str(p8)

    if p7 == 0:
        $ bgi_img = bgi_char_pos[p8]["name"]
    else:
        $ bgi_img = p7
        $ bgi_char_pos[p8]["name"] = bgi_img

    $ bgi_char_pos[p8]["x2"] = bgi_x2
    $ bgi_char_pos[p8]["y2"] = bgi_y2
    $ bgi_char_pos[p8]["angle"] = bgi_r2
    $ bgi_char_pos[p8]["trig"] = 1

    $ renpy.show(name=bgi_img,at_list=[bgitrans_f_2c2(bgi_trans_time,bgi_x2,bgi_y2,bgi_r1,bgi_r2)],tag=bgi_tag)
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

label bgi_f_2c4:
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if bgi_sakura == 1:
        $ p0 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0
    $ bgi_r2 = -1 * p3
    $ bgi_x2 = p6 - bgi_char_pos[p8]["xa"]
    $ bgi_y2 = p5 - bgi_char_pos[p8]["ya"]
    $ bgi_r1 = bgi_char_pos[p8]["angle"]
    $ bgi_tag = str(p8)

    if p7 == 0:
        $ bgi_img = bgi_char_pos[p8]["name"]
    else:
        $ bgi_img = p7
        $ bgi_char_pos[p8]["name"] = bgi_img

    $ bgi_char_pos[p8]["x2"] = bgi_x2
    $ bgi_char_pos[p8]["y2"] = bgi_y2
    $ bgi_char_pos[p8]["angle"] = bgi_r2
    $ bgi_char_pos[p8]["trig"] = 1

    $ renpy.show(name=bgi_img,at_list=[bgitrans_pos(bgi_x2,bgi_y2)],tag=bgi_tag)
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

label bgi_f_2c6:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if bgi_sakura == 1:
        $ p0 = bgi_stack.pop()

    $ bgi_img = p3.lower()
    $ bgi_tag = str(p4)
    $ bgi_trans_time = p2/1000.0

    if bgi_char_pos[p4] == 0 or bgi_char_pos[p4]["name"][:2] != bgi_img[:2]:
        return

    $ bgi_char_pos[p4]["name"] = bgi_img
    $ bgi_char_pos[p4]["trig"] = 1
    $ renpy.show(name=bgi_img,at_list=[bgitrans_pos(bgi_char_pos[p4]["x2"],bgi_char_pos[p4]["y2"])],tag=bgi_tag,zorder=bgi_char_pos[p4]["z"])

    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

transform bgitrans_f_2c8(t, x2, y2):
    parallel:
        linear t alpha 0
    parallel:
        linear t xoffset x2
    parallel:
        linear t yoffset y2


label bgi_f_2c8:
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    if bgi_sakura == 1:
        $ p0 = bgi_stack.pop()

    $ bgi_tag = str(p8)
    $ bgi_img = bgi_char_pos[p8]["name"]
    $ bgi_trans_time = p2/1000.0
    $ bgi_x2 = p6 - bgi_char_pos[p8]["xa"]
    $ bgi_y2 = p5 - bgi_char_pos[p8]["ya"]

    if p5 ==0 and p6 == 0:
        $ renpy.hide(name=bgi_tag)
        $ renpy.with_statement(Dissolve(bgi_trans_time))
        return

    if p7:
        $ renpy.show(name=bgi_img,at_list=[bgitrans_f_2c8(bgi_trans_time,bgi_x2,bgi_y2)],tag=bgi_tag)
    if p1:
        $ renpy.pause(bgi_trans_time)

    $ renpy.hide(name=bgi_tag)
    return

label bgi_f_2ca:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_2dc:
    $ p1 = bgi_stack.pop()
    $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

label bgi_f_2df:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_2f8:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

transform bgitrans_f_300_2(t, xa, ya, x2, y2, z2, a):
    alpha 0
    xanchor xa
    yanchor ya
    xpos 0.5
    ypos 0.5
    xoffset x2
    yoffset y2
    zoom z2
    parallel:
        linear t alpha a
    on hide:
        alpha a
label bgi_f_300:
    $ p16 = bgi_stack.pop()
    $ p15 = bgi_stack.pop()
    $ p14 = bgi_stack.pop()
    $ p13 = bgi_stack.pop()
    $ p12 = bgi_stack.pop()
    $ p11 = bgi_stack.pop()
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()




    $ bgi_trans_time = p2/1000.0
    $ bgi_img = p15.lower()
    $ bgi_tag = str(p16)
    $ bgi_zorder = p3
    $ bgi_alpha = (255 - p4) / 255.0
    $ bgi_z2 = bgi_cal_zoom(p11)

    if bgi_img == 'white' or bgi_img == 'black' or bgi_img == 'red':
        $ bgi_image_size = [1280,960]
    else:
        $ bgi_image_size = vita_image_size(bgi_img)

    $ bgi_x = p13
    $ bgi_y = p12
    $ bgi_f30x_pos[p16] = {}
    $ bgi_f30x_pos[p16]["name"] = bgi_img
    $ bgi_f30x_pos[p16]["xanchor"] = p10*1.0/bgi_image_size[0]
    $ bgi_f30x_pos[p16]["yanchor"] = p9*1.0/bgi_image_size[1]
    $ bgi_f30x_pos[p16]["x2"] = bgi_x
    $ bgi_f30x_pos[p16]["y2"] = bgi_y
    $ bgi_f30x_pos[p16]["z"] = bgi_zorder
    $ bgi_f30x_pos[p16]["angle"] = -1*p8
    $ bgi_f30x_pos[p16]["alpha"] = bgi_alpha
    $ bgi_f30x_pos[p16]["trig"] = 0


    if bgi_img.startswith('bg'):
        return
    if bgi_img.startswith('aula'):
        return
    if bgi_img == 'black' and p14 != 0:
        return

    $ renpy.show(name=bgi_img,at_list=[bgitrans_f_300_2(bgi_trans_time,bgi_f30x_pos[p16]["xanchor"],bgi_f30x_pos[p16]["yanchor"],bgi_x,bgi_y,bgi_z2,bgi_alpha)],tag=bgi_tag,zorder=bgi_zorder,layer='f30x')

    if p1:
        $ renpy.pause(bgi_trans_time)

    return

label bgi_f_302:
    $ p19 = bgi_stack.pop()
    $ p18 = bgi_stack.pop()
    $ p17 = bgi_stack.pop()
    $ p16 = bgi_stack.pop()
    $ p15 = bgi_stack.pop()
    $ p14 = bgi_stack.pop()
    $ p13 = bgi_stack.pop()
    $ p12 = bgi_stack.pop()
    $ p11 = bgi_stack.pop()
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_306:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_tag = str(p3)
    $ bgi_trans_time = p2/1000.0

    $ renpy.hide(name=bgi_tag,layer='f30x')
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

transform bgitrans_f_308(t, xa, ya, x2, y2, z2):
    xanchor xa
    yanchor ya
    xpos 0.5
    ypos 0.5
    zoom 1.0

    parallel:
        linear t zoom z2
    parallel:
        linear t xoffset x2
    parallel:
        linear t yoffset y2

label bgi_f_308:
    $ p10 = bgi_stack.pop()
    $ p9 = bgi_stack.pop()
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0
    $ bgi_img = bgi_f30x_pos[p10]["name"]
    $ bgi_tag = str(p10)
    $ bgi_zorder = bgi_f30x_pos[p10]["z"]
    $ bgi_x2 = p9
    $ bgi_y2 = p8
    $ bgi_z2 = bgi_cal_zoom(p7)

    $ renpy.show(name=bgi_img,at_list=[bgitrans_f_308(bgi_trans_time,bgi_f30x_pos[p10]["xanchor"],bgi_f30x_pos[p10]["yanchor"],bgi_x2,bgi_y2,bgi_z2)],tag=bgi_tag,layer='f30x')
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))

    return

transform bgi_f_30c_1(t):
    xanchor 0
    yanchor 0
    xpos 0.0
    ypos 0.0
    xoffset 0
    yoffset 0
    block:
        xalign 0.0
        linear t xalign 1.0
        repeat

transform bgi_f_30c_2(t):
    xanchor 0
    yanchor 0
    xpos 0.0
    ypos 0.0
    xoffset 0
    yoffset 0
    block:
        xalign 1.0
        linear t xalign 0.0
        repeat

label bgi_f_30c:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()


    $ bgi_tag = str(p2)
    $ bgi_img = bgi_f30x_pos[p2]["name"]
    $ bgi_trans_time = vita_image_size(bgi_img)[0]/abs(p1)
    $ print(bgi_trans_time)

    if p1 > 0:
        $ renpy.show(name=bgi_img,at_list=[bgi_f_30c_1(bgi_trans_time)],tag=bgi_tag,layer='f30x')
    else:
        $ renpy.show(name=bgi_img,at_list=[bgi_f_30c_2(bgi_trans_time)],tag=bgi_tag,layer='f30x')
    return




label bgi_f_30e:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.show_layer_at(at_list=vpunch,layer='master')
    return

label bgi_f_31f:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return


transform bgitrans_f_340(t, b):
    linear t blur b

label bgi_f_340:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0
    $ bgi_blur = p3*1.0
    $ renpy.show_layer_at(at_list=[bgitrans_f_340(bgi_trans_time,bgi_blur)],layer='master')
    $ renpy.show_layer_at(at_list=[bgitrans_f_340(bgi_trans_time,bgi_blur)],layer='f30x')
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

transform bgitrans_f_348(t):
    linear t blur None

label bgi_f_348:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ bgi_trans_time = p2/1000.0
    $ bgi_blur = None
    $ renpy.show_layer_at(at_list=[bgitrans_f_348(bgi_trans_time)],layer='master')
    $ renpy.show_layer_at(at_list=[bgitrans_f_348(bgi_trans_time)],layer='f30x')
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return


label bgi_f_350:
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_351:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_358:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

transform bgitrans_f_380(t, c):
    matrixcolor TintMatrix("#fff")
    linear t matrixcolor TintMatrix(c)

label bgi_f_380:
    $ p8 = bgi_stack.pop()
    $ p7 = bgi_stack.pop()
    $ p6 = bgi_stack.pop()
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0
    if p4 == 256:
        $ p4 = 255
    if p5 == 256:
        $ p5 = 255
    if p6 == 256:
        $ p6 = 255
    $ bgi_tint_color = Color((p4, p5, p6, p7))
    $ renpy.show_layer_at(at_list=[bgitrans_f_380(bgi_trans_time,bgi_tint_color)],layer='master')
    $ renpy.show_layer_at(at_list=[bgitrans_f_380(bgi_trans_time,bgi_tint_color)],layer='f30x')
    $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

transform bgitrans_f_388(t):
    linear t matrixcolor IdentityMatrix()

label bgi_f_388:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0

    $ renpy.scene(layer='f39x')

    $ renpy.show_layer_at(at_list=[bgitrans_f_388(bgi_trans_time)],layer='master')
    $ renpy.show_layer_at(at_list=[bgitrans_f_388(bgi_trans_time)],layer='f30x')
    if p1:
        $ renpy.with_statement(Dissolve(bgi_trans_time))
    return

label bgi_f_390:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_391:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ renpy.show('white',tag='f392',layer='f39x')
    if p1:
        $ renpy.with_statement(Dissolve(p2/1000.0))
    return

label bgi_f_392:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    $ renpy.show('white',tag='f392',layer='f39x')
    if p1:
        $ renpy.with_statement(Dissolve(p2/1000.0))
    return

transform bgitrans_f_393(t):
    linear t matrixcolor SaturationMatrix(0.0)

label bgi_f_393:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ bgi_trans_time = p2/1000.0

    $ renpy.show_layer_at(at_list=[bgitrans_f_393(bgi_trans_time)],layer='master')
    if p1:
        $ renpy.pause(bgi_trans_time)
    return

label bgi_f_394:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3c0:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3c1:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3c7:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3d0:
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3d2:
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3d4:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3d6:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3d8:
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3f0:
    $ p5 = bgi_stack.pop()
    $ p4 = bgi_stack.pop()
    $ p3 = bgi_stack.pop()
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()
    return

label bgi_f_3f1:
    $ p2 = bgi_stack.pop()
    $ p1 = bgi_stack.pop()

    $ renpy.show_layer_at(at_list=[Move((p1*15, p2*10), (-15*p1, -10*p2), .125, bounce=True, repeat=True, delay=.475)],layer='master')
    $ renpy.pause(0.5)
    show layer master:
        xoffset 0
        yoffset 0
    return
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
