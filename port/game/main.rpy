label lmain:

    $ bgi_load_base()
    $ bgi_push_dword(4)
    $ bgi_add()
    $ bgi_store_base()
    $ bgi_push_offset('lmain_0052c')
    $ bgi_reg_exception_handler()
    $ bgi_line('main.bss', '11')
    $ bgi_push_dword(1)
    call bgi_f_122
    $ bgi_line('main.bss', '12')
    $ bgi_push_dword(1)
    call bgi_f_123
    $ bgi_line('main.bss', '15')
    $ bgi_push_dword(1)
    call bgi_f_16c
    $ bgi_line('main.bss', '19')
    $ bgi_push_dword(1)
    $ bgi_push_dword(34)
    $ bgi_push_dword(0)
    call bgi_f_14c
    $ bgi_line('main.bss', '30')
    $ bgi_push_dword(230)
    $ bgi_f_0e7()
    $ bgi_push_dword(0)
    $ bgi_eq()
    $ bgi_push_offset('lmain_000f4')
    $ bgi_jc(0)
    $ bgi_line('main.bss', '33')
    $ bgi_push_string('1-1_0710_Dream')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '34')
    $ bgi_push_offset('lmain_000f4')
    $ bgi_jmp()

label lmain_000f4:
    $ bgi_line('main.bss', '38')
    $ bgi_f_169()
    $ bgi_push_base_offset(4)
    $ bgi_move_arg(2)
    $ bgi_line('main.bss', '41')
    $ bgi_push_dword(0)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_00194')
    $ bgi_jc(0)
    $ bgi_line('main.bss', '43')
    $ bgi_push_string('1-2_0000')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '44')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '47')
    $ bgi_push_offset('lmain_001c0')
    $ bgi_jmp()

label lmain_00194:
    $ bgi_push_dword(1)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_00208')
    $ bgi_jc(0)

label lmain_001c0:
    $ bgi_line('main.bss', '49')
    $ bgi_push_string('2_0000')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '50')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '53')
    $ bgi_push_offset('lmain_00234')
    $ bgi_jmp()

label lmain_00208:
    $ bgi_push_dword(2)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_0027c')
    $ bgi_jc(0)

label lmain_00234:
    $ bgi_line('main.bss', '55')
    $ bgi_push_string('3_0000')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '56')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '59')
    $ bgi_push_offset('lmain_002a8')
    $ bgi_jmp()

label lmain_0027c:
    $ bgi_push_dword(3)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_002f0')
    $ bgi_jc(0)

label lmain_002a8:
    $ bgi_line('main.bss', '61')
    $ bgi_push_string('4_0000')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '62')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '65')
    $ bgi_push_offset('lmain_0031c')
    $ bgi_jmp()

label lmain_002f0:
    $ bgi_push_dword(4)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_00364')
    $ bgi_jc(0)

label lmain_0031c:
    $ bgi_line('main.bss', '67')
    $ bgi_push_string('5_0000')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '68')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '71')
    $ bgi_push_offset('lmain_00390')
    $ bgi_jmp()

label lmain_00364:
    $ bgi_push_dword(5)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_003d8')
    $ bgi_jc(0)

label lmain_00390:
    $ bgi_line('main.bss', '73')
    $ bgi_push_string('6-1')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '74')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '77')
    $ bgi_push_offset('lmain_00404')
    $ bgi_jmp()

label lmain_003d8:
    $ bgi_push_dword(6)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_0044c')
    $ bgi_jc(0)

label lmain_00404:
    $ bgi_line('main.bss', '79')
    $ bgi_push_string('7-1_SunFlower')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '80')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '83')
    $ bgi_push_offset('lmain_00478')
    $ bgi_jmp()

label lmain_0044c:
    $ bgi_push_dword(7)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_004c0')
    $ bgi_jc(0)

label lmain_00478:
    $ bgi_line('main.bss', '85')
    $ bgi_push_string('7-2_Wonderful')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '86')
    $ bgi_push_offset('lmain_00510')
    $ bgi_jmp()
    $ bgi_line('main.bss', '89')
    $ bgi_push_offset('lmain_004ec')
    $ bgi_jmp()

label lmain_004c0:
    $ bgi_push_dword(8)
    $ bgi_push_base_offset(4)
    $ bgi_load(2)
    $ bgi_eq()
    $ bgi_push_offset('lmain_00510')
    $ bgi_jc(0)

label lmain_004ec:
    $ bgi_line('main.bss', '91')
    $ bgi_push_string('7-3_EndofSky')
    $ bgi_f_0f0()
    $ bgi_line('main.bss', '94')

label lmain_00510:
    $ bgi_line('main.bss', '97')
    call bgi_f_0f4
    $ bgi_line('main.bss', '100')

label lmain_0052c:
    $ bgi_unreg_exception_handler()
    $ bgi_load_base()
    $ bgi_push_dword(4)
    $ bgi_sub()
    $ bgi_store_base()
    return
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
