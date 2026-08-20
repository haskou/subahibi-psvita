label lmakerlogo:

    $ bgi_load_base()
    $ bgi_push_dword(4)
    $ bgi_add()
    $ bgi_store_base()
    $ bgi_push_offset('lmakerlogo_00420')
    $ bgi_reg_exception_handler()
    $ bgi_line('MakerLogo.bss', '10')
    $ bgi_push_dword(1)
    call bgi_f_124
    $ bgi_line('MakerLogo.bss', '12')
    call bgi_f_119
    $ bgi_line('MakerLogo.bss', '14')
    $ bgi_push_dword(200)
    $ bgi_f_0e7()
    $ bgi_push_dword(0)
    $ bgi_eq()
    $ bgi_push_offset('lmakerlogo_000ac')
    $ bgi_jc(0)
    $ bgi_line('MakerLogo.bss', '17')
    $ bgi_push_dword(0)
    call bgi_f_120
    $ bgi_line('MakerLogo.bss', '18')
    $ bgi_push_offset('lmakerlogo_000ac')
    $ bgi_jmp()

label lmakerlogo_000ac:
    $ bgi_line('MakerLogo.bss', '20')
    $ bgi_push_dword(1000)
    $ bgi_push_string('white')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '22')
    $ bgi_push_dword(0)
    $ bgi_push_dword(1500)
    $ bgi_push_dword(10)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_string('logo1')
    $ bgi_push_dword(1)
    call bgi_f_2c0
    $ bgi_line('MakerLogo.bss', '23')
    $ bgi_push_dword(1500)
    $ bgi_push_string('logo1')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '25')
    $ bgi_push_dword(1)
    $ bgi_push_dword(0)
    $ bgi_push_dword(5)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(40)
    $ bgi_push_dword(-1)
    $ bgi_mul()
    $ bgi_push_dword(22)
    $ bgi_push_dword(-1)
    $ bgi_mul()
    $ bgi_push_string('logo3')
    $ bgi_push_dword(0)
    call bgi_f_2c0
    $ bgi_line('MakerLogo.bss', '27')
    $ bgi_push_dword(0)
    $ bgi_push_dword(1500)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_string('logo3')
    $ bgi_push_dword(0)
    call bgi_f_2c2
    $ bgi_line('MakerLogo.bss', '28')
    $ bgi_push_dword(0)
    $ bgi_push_dword(1300)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(0)
    $ bgi_push_dword(1)
    call bgi_f_2c8
    $ bgi_line('MakerLogo.bss', '29')
    $ bgi_push_dword(1)
    call bgi_f_2dc
    $ bgi_line('MakerLogo.bss', '31')
    $ bgi_push_dword(1500)
    $ bgi_push_string('logo2')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '33')
    $ bgi_push_dword(2000)
    call bgi_f_110
    $ bgi_line('MakerLogo.bss', '35')
    $ bgi_push_dword(1500)
    $ bgi_push_string('white')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '38')
    $ bgi_push_dword(1000)
    call bgi_f_110
    $ bgi_line('MakerLogo.bss', '41')
    call bgi_f_119
    $ bgi_line('MakerLogo.bss', '43')
    $ bgi_push_dword(1500)
    $ bgi_push_string('warning')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '45')
    $ bgi_push_dword(5000)
    call bgi_f_110
    $ bgi_line('MakerLogo.bss', '47')
    $ bgi_push_dword(1500)
    $ bgi_push_string('warning2')
    call bgi_f_280
    $ bgi_line('MakerLogo.bss', '49')
    $ bgi_push_dword(5000)
    call bgi_f_110
    $ bgi_line('MakerLogo.bss', '51')
    $ bgi_push_dword(1500)
    call bgi_f_288
    $ bgi_line('MakerLogo.bss', '53')
    $ bgi_push_dword(1)
    call bgi_f_120
    $ bgi_line('MakerLogo.bss', '55')
    $ bgi_push_dword(0)
    call bgi_f_124
    $ bgi_line('MakerLogo.bss', '59')

label lmakerlogo_00420:
    $ bgi_unreg_exception_handler()
    $ bgi_load_base()
    $ bgi_push_dword(4)
    $ bgi_sub()
    $ bgi_store_base()
    return
# Decompiled by unrpyc: https://github.com/CensoredUsername/unrpyc
