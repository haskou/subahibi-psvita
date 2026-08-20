# Vita-only readability adjustments. Translation text is embedded directly in
# copied RPYC files during the build and is not looked up at runtime.


init 900 python:
    # The 1280x960 layout is letterboxed to 725x544 on Vita. Keep the readable
    # 36 px dialogue size, but give longer English lines substantially more
    # horizontal and vertical room.
    gui.textbox_height = 320
    gui.dialogue_xpos = 110
    gui.dialogue_ypos = 38
    gui.dialogue_width = 1060
    gui.name_xpos = 110
    gui.name_ypos = 8

    style.say_dialogue.size = 40
    style.say_label.size = 42
    style.nvl_dialogue.size = 38

    style.navigation_button_text.size = 42
    style.navigation_button_text.outlines = [(2, "#000000cc", 0, 0)]

    # File-slot text from the desktop layout becomes unreadable after the
    # 1280x960 interface is scaled to the Vita display.
    style.game_menu_label_text.size = 48
    style.page_label_text.size = 38
    style.page_button_text.size = 36
    style.slot_button_text.size = 34
    style.slot_time_text.size = 32
    style.slot_name_text.size = 34

    # History is rendered inside the same scaled 4:3 viewport as dialogue.
    # Match its body text to the readable dialogue size and let the viewport
    # scroll instead of shrinking entries to fit more of them at once.
    style.history_text.size = 40
    style.history_text.line_spacing = 6
    style.history_name_text.size = 42

    # Full-screen dissolves make every menu action render both 1280x960
    # screens on the Vita. Menu changes are immediate instead.
    config.enter_transition = None
    config.exit_transition = None
    config.intra_transition = None
    config.main_game_transition = None
    config.game_main_transition = None

    # Use a fixed 16:9 virtual canvas containing an unscaled 1280x960 game
    # rectangle. Vita then scales the complete 1694x960 canvas to 960x544,
    # making the game 725x544 with 117 px physical pillarboxes. Unlike a layer
    # transform, this geometry cannot be removed by BGI scene/layer commands.
    config.screen_width = 1694
    config.screen_height = 960
    if "vita_overlay" not in config.top_layers:
        config.top_layers.append("vita_overlay")
        renpy.game.context().scene_lists.after_setstate()
    for layer_name in config.layers:
        config.layer_clipping[layer_name] = (207, 0, 1280, 960)
    if "vita_sidebar" not in config.overlay_screens:
        config.overlay_screens.append("vita_sidebar")

    # Handle Vita gameplay shortcuts in quick_menu using the raw SDL controller
    # events. This also lets L + Select differ from either button on its own.
    for event_name in (
        "pad_b_press",
        "pad_y_press",
        "pad_leftshoulder_press",
        "repeat_pad_leftshoulder_press",
        "pad_back_press",
        "repeat_pad_back_press",
        "pad_rightshoulder_press",
        "repeat_pad_rightshoulder_press",
    ):
        config.pad_bindings[event_name] = []

    # Touching a sidebar button gives it mouse focus. Stock SayBehavior ignores
    # dialogue dismissal while another displayable owns that focus, which also
    # prevents the hidden interface from being restored. Accept the ordinary
    # dismiss inputs in the unfocused path as well. Button clicks still consume
    # their own event before it can reach SayBehavior.
    config.keymap["dismiss_unfocused"] = list(config.keymap["dismiss"])

    # Directional controller events may only move focus while a menu or a
    # choice screen is active. This matters after suspend/resume, when SDL can
    # deliver a stale stick/D-pad repeat that would otherwise focus one of the
    # touch-only sidebar buttons. D-pad Down advances dialogue, but its repeats
    # do not, so one press always advances exactly one interaction.
    def vita_map_pad_event(event_name):
        mapped = tuple(config.pad_bindings.get(event_name, ()))
        navigation_active = (
            renpy.context()._menu or
            renpy.get_screen("choice") is not None
        )

        if navigation_active:
            return mapped

        mapped = tuple(
            name for name in mapped
            if not name.startswith(("focus_", "bar_", "viewport_"))
        )

        if "dismiss" in mapped and "dismiss_unfocused" not in mapped:
            mapped += ("dismiss_unfocused",)

        if event_name == "pad_dpdown_press":
            return mapped + ("dismiss", "dismiss_unfocused")

        return mapped

    config.map_pad_event = vita_map_pad_event

    style.pref_label_text.size = 38
    style.radio_button_text.size = 34
    style.check_button_text.size = 34
    style.slider_button_text.size = 34
    style.mute_all_button_text.size = 34

    # Confirmation prompts are modal on Vita and must remain readable after the
    # 1694x960 canvas is scaled to the physical display.
    style.vita_confirm_frame.xsize = 900
    style.vita_confirm_frame.ysize = 420
    style.vita_confirm_prompt_text.size = 44
    style.vita_confirm_prompt_text.xsize = 780
    style.vita_confirm_button.xsize = 260
    style.vita_confirm_button.ysize = 100
    style.vita_confirm_button_text.size = 40

    # Keep enough decoded images for nearby scene changes without allowing the
    # desktop default to consume most of the Vita process memory.
    config.image_cache_size = None
    config.image_cache_size_mb = 96

    # The overlay uses the 1694x960 virtual canvas. These values become roughly
    # 108x59 physical pixels and fit inside each 207-unit virtual pillarbox.
    vita_sidebar_inset = 9
    vita_sidebar_spacing = 11
    style.vita_side_button.xsize = 190
    style.vita_side_button.ysize = 104
    style.vita_side_button.xpadding = 9
    style.vita_side_button.ypadding = 5
    style.vita_side_button.background = Solid("#080808b0")
    style.vita_side_button.hover_background = Solid("#64324ce6")
    style.vita_side_button.keyboard_focus = False
    style.vita_side_button_text.size = 35
    style.vita_side_button_text.color = "#ffffff"
    style.vita_side_button_text.hover_color = "#ffffff"
    style.vita_side_button_text.outlines = [(2, "#000000ee", 0, 0)]
    style.vita_side_button_text.text_align = 0.5
    style.vita_side_button_text.xalign = 0.5
    style.vita_side_button_text.yalign = 0.5


style vita_side_button is quick_button
style vita_side_button_text is quick_button_text
style vita_confirm_frame is confirm_frame
style vita_confirm_prompt is confirm_prompt
style vita_confirm_prompt_text is confirm_prompt_text
style vita_confirm_button is confirm_button
style vita_confirm_button_text is confirm_button_text


default vita_l_held = False


# The source navigation screen contains desktop-only Help and a game-specific
# Extra entry whose gallery dependencies are not present in the Vita payload.
# Replace it completely so no hidden action from the compiled screen remains.
screen navigation():
    vbox:
        style_prefix "navigation"
        xpos gui.navigation_xpos
        xoffset -24
        yalign 0.5
        spacing gui.navigation_spacing

        if main_menu:
            textbutton "Start" action Start()
        else:
            textbutton "History" action ShowMenu("history")
            textbutton "Save" action ShowMenu("save")

        textbutton "Load" action ShowMenu("load")
        textbutton "Preferences" action ShowMenu("preferences")

        if _in_replay:
            textbutton "End Replay" action EndReplay(confirm=True)
        elif not main_menu:
            textbutton "Main Menu" action MainMenu()

        textbutton "About" action ShowMenu("about")


# Do not expose the source game's untranslated gui.about value. The port only
# needs a compact technical description on this screen.
screen about():
    tag menu

    use game_menu("About", scroll="viewport"):
        style_prefix "about"

        vbox:
            spacing 24
            label "Subahibi"
            text "Version [config.version!t]"
            text "PS Vita port powered by Ren'Py 7.4.9 and RenPy-Vita 7."


# Replace the desktop confirmation prompt. Raw Vita events are consumed here
# so directional input cannot move focus through the game menu underneath the
# modal overlay. Touch remains available through the two ordinary buttons.
screen confirm(message, yes_action, no_action):
    modal True
    zorder 300
    style_prefix "vita_confirm"

    default vita_confirm_yes = False

    add "gui/overlay/confirm.png"

    frame:
        xalign 0.5
        yalign 0.5

        vbox:
            xalign 0.5
            yalign 0.5
            spacing 48

            label _(message):
                style "vita_confirm_prompt"
                xalign 0.5

            hbox:
                xalign 0.5
                spacing 100

                textbutton _("Yes"):
                    id "confirm_yes"
                    selected vita_confirm_yes
                    action yes_action

                textbutton _("No"):
                    id "confirm_no"
                    selected not vita_confirm_yes
                    default_focus 100
                    action no_action

    key ["focus_left", "focus_up", "pad_dpleft_press", "pad_dpup_press"] action SetScreenVariable("vita_confirm_yes", True)
    key ["focus_right", "focus_down", "pad_dpright_press", "pad_dpdown_press"] action SetScreenVariable("vita_confirm_yes", False)
    key "pad_a_press" action If(vita_confirm_yes, yes_action, no_action)
    key "pad_b_press" action no_action
    key "game_menu" action no_action

    timer 0.01 action Function(renpy.set_focus, "confirm", "confirm_no")


screen quick_menu():
    zorder 100

    if quick_menu:
        key "pad_b_press" action HideInterface()
        key "pad_y_press" action ShowMenu("history")
        key "pad_x_press" action Preference("auto-forward", "toggle")
        key "pad_rightshoulder_press" action Skip()
        key "pad_leftshoulder_press" action SetVariable("vita_l_held", True)
        key "pad_leftshoulder_release" action If(
            vita_l_held,
            [SetVariable("vita_l_held", False), Rollback()],
            NullAction()
        )
        key "pad_back_press" action If(
            vita_l_held,
            [SetVariable("vita_l_held", False), QuickLoad()],
            QuickSave()
        )



screen vita_sidebar():
    layer "vita_overlay"
    zorder 100

    if quick_menu:
        vbox:
            style_prefix "vita_side"
            xpos vita_sidebar_inset
            yalign 0.28
            spacing vita_sidebar_spacing

            textbutton "SELECT\nQ.S" action QuickSave() keyboard_focus False
            textbutton "L+SELECT\nQ.L" action QuickLoad() keyboard_focus False

        vbox:
            style_prefix "vita_side"
            xalign 1.0
            xoffset -vita_sidebar_inset
            yalign 0.5
            spacing vita_sidebar_spacing

            textbutton "{color=#35dfcf}△{/color}  Hist" action ShowMenu("history") keyboard_focus False
            textbutton "{color=#e59ac8}□{/color}  Auto" action Preference("auto-forward", "toggle") keyboard_focus False
            textbutton "R  Skip" action Skip() keyboard_focus False
            textbutton "START\nMenu" action ShowMenu() keyboard_focus False
            textbutton "{color=#ef6f72}○{/color}  Hide" action HideInterface() keyboard_focus False


screen preferences():
    tag menu

    use game_menu("Preferences", scroll="viewport"):
        vbox:
            spacing 24

            hbox:
                spacing 80

                vbox:
                    style_prefix "radio"
                    label "Rollback Side"
                    textbutton "Disable" action Preference("rollback side", "disable")
                    textbutton "Left" action Preference("rollback side", "left")
                    textbutton "Right" action Preference("rollback side", "right")

                vbox:
                    style_prefix "check"
                    label "Skip"
                    textbutton "Unseen Text" action Preference("skip", "toggle")
                    textbutton "After Choices" action Preference("after choices", "toggle")
                    textbutton "Transitions" action InvertSelected(Preference("transitions", "toggle"))

            null height 20

            hbox:
                spacing 60

                vbox:
                    spacing 12
                    label "Text Speed" style "pref_label"
                    bar value Preference("text speed") xsize 420

                    label "Auto-Forward Time" style "pref_label"
                    bar value Preference("auto-forward time") xsize 420

                vbox:
                    spacing 12

                    if config.has_music:
                        label "Music Volume" style "pref_label"
                        bar value Preference("music volume") xsize 420

                    if config.has_sound:
                        label "Sound Volume" style "pref_label"
                        bar value Preference("sound volume") xsize 420

                    if config.has_voice:
                        label "Voice Volume" style "pref_label"
                        bar value Preference("voice volume") xsize 420

                    if config.has_music or config.has_sound or config.has_voice:
                        textbutton "Mute All" action Preference("all mute", "toggle") style "mute_all_button"
