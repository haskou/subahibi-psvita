# Vita-only readability adjustments. Translation text is embedded directly in
# copied RPYC files during the build and is not looked up at runtime.


init -1800 python:
    # Ren'Py normally walks every file in every RPA twice during startup: once
    # to create 33,000+ audio.* variables and once to register every image.
    # The BGI compatibility layer uses explicit audio paths, so the audio
    # namespace is unnecessary. Images are all uniquely named WebP files and
    # can be resolved in constant time from the already-loaded RPA index when
    # they are first shown.
    config.audio_directory = None
    config.images_directory = None

    def vita_lazy_image(what):
        if not isinstance(what, tuple):
            return None

        image_name = " ".join(what).lower()
        filename = "images/{}.webp".format(image_name)

        if renpy.loadable(filename):
            displayable = renpy.display.im.Image(filename)
            # Registering the displayable also repairs ImageReference objects
            # restored directly from a save, which do not pass through
            # config.missing_show before they are rendered.
            renpy.display.image.register_image(what, displayable)
            return displayable

        return None

    def vita_lazy_missing_show(name, what, layer):
        return vita_lazy_image(what)

    _vita_image_reference_find_target = renpy.display.image.ImageReference.find_target

    def vita_lazy_find_image_reference(self):
        name = self.name
        if not isinstance(name, tuple):
            name = tuple(name.split())
        if name not in renpy.display.image.images:
            vita_lazy_image(name)
        return _vita_image_reference_find_target(self)

    renpy.display.image.ImageReference.find_target = vita_lazy_find_image_reference

    config.missing_show = vita_lazy_missing_show


init 900 python:
    # --- Vita menu palette (white / blue) -----------------------------------
    # One state language shared by every light menu surface:
    #   idle      dark ink text, no fill
    #   focus     dark-blue bold, underlined text
    #   selected  blue bold text (the active item)
    #   both      darker-blue bold, underlined text
    # Text always remains dark enough for the real white menu surface.
    VITA_INK = "#3d4654"
    VITA_INK_FOCUS = "#003b73"
    VITA_FOCUS_FILL = "#c7e8ff"
    VITA_SELECTED_FILL = "#8fd3f4"
    VITA_SELECTED_FILL_HOVER = "#72c3ed"
    VITA_SELECTED_TEXT = "#004b80"
    VITA_SELECTED_HOVER_TEXT = "#002c5c"
    VITA_PANEL = "#f7f9fb"

    def vita_contrast(fg, bg):
        """WCAG 2.x contrast ratio between two opaque #rrggbb colours."""
        def luma(color):
            scaled = [int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
            channel = [
                c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in scaled
            ]
            return (
                0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]
            )

        one, other = luma(fg), luma(bg)
        if one < other:
            one, other = other, one
        return (one + 0.05) / (other + 0.05)

    # Every text/background pair used by the menu styles below must pass
    # WCAG AA (4.5:1). This runs at every boot, so a future colour tweak that
    # breaks legibility fails loudly instead of shipping unreadable menus.
    for vita_fg, vita_bg in (
        (VITA_INK, VITA_PANEL),
        (VITA_INK_FOCUS, VITA_FOCUS_FILL),
        (VITA_SELECTED_TEXT, VITA_SELECTED_FILL),
        (VITA_SELECTED_HOVER_TEXT, VITA_SELECTED_FILL_HOVER),
        ("#26303c", "#eef4fa"),
        ("#23445f", "#bcdcff"),
        (VITA_INK_FOCUS, VITA_PANEL),
    ):
        if vita_contrast(vita_fg, vita_bg) < 4.5:
            raise Exception(
                "Vita UI palette fails WCAG AA contrast: {} on {}".format(
                    vita_fg, vita_bg
                )
            )

    style.create("vita_navigation_panel", "empty")

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

    # One restrained navigation language is shared by the main menu, game
    # menus and Return.
    style.navigation_button_text.font = gui.interface_text_font
    style.navigation_button_text.size = 38
    style.navigation_button_text.outlines = []
    style.navigation_button.xsize = 260
    style.navigation_button.ysize = 58
    style.navigation_button.xpadding = 18
    style.navigation_button.ypadding = 5
    style.navigation_button.background = Solid("#00000000")
    style.navigation_button.hover_background = Solid(VITA_FOCUS_FILL + "80")
    style.navigation_button.selected_idle_background = Solid(VITA_SELECTED_FILL + "80")
    style.navigation_button.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "90")
    style.navigation_button_text.color = VITA_INK
    style.navigation_button_text.hover_color = VITA_INK_FOCUS
    style.navigation_button_text.hover_bold = True
    style.navigation_button_text.hover_underline = True
    style.navigation_button_text.hover_outlines = []
    style.navigation_button_text.selected_idle_color = VITA_SELECTED_TEXT
    style.navigation_button_text.selected_idle_bold = True
    style.navigation_button_text.selected_idle_outlines = []
    style.navigation_button_text.selected_hover_color = VITA_SELECTED_HOVER_TEXT
    style.navigation_button_text.selected_hover_bold = True
    style.navigation_button_text.selected_hover_underline = True
    style.navigation_button_text.selected_hover_outlines = []
    style.navigation_button_text.insensitive_color = "#64707f"

    style.vita_navigation_panel.xsize = 286
    style.vita_navigation_panel.xpadding = 10
    style.vita_navigation_panel.ypadding = 14
    style.vita_navigation_panel.background = Solid("#f7f9fbb8")

    # Loading a save must return directly to the saved game state. Reopening
    # the menu that initiated a runtime reload is desktop-oriented behaviour
    # and is confusing on Vita, where it looks as if loading did nothing.
    config.reload_menu = False

    # Vita screenshots contain the complete 16:9 canvas, including the black
    # pillarboxes. Store and display them at the same aspect ratio instead of
    # stretching them vertically into the desktop GUI's 4:3 thumbnail size.
    config.thumbnail_width = 256
    config.thumbnail_height = 144
    gui.slot_button_height = 214

    # File-slot text from the desktop layout becomes unreadable after the
    # 1280x960 interface is scaled to the Vita display.
    style.game_menu_label_text.size = 48
    style.page_label_text.size = 38
    style.page_button_text.size = 36
    style.slot_button_text.size = 34
    style.slot_time_text.size = 32
    style.slot_name_text.size = 34
    style.slot_button.hover_background = Solid("#b9ddffd0")
    style.slot_button.selected_idle_background = Solid(VITA_SELECTED_FILL + "f0")
    style.slot_button.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "f2")
    style.slot_button_text.color = "#23445f"
    style.slot_button_text.hover_color = VITA_INK_FOCUS
    style.slot_button_text.selected_idle_color = VITA_SELECTED_TEXT
    style.slot_button_text.selected_hover_color = VITA_SELECTED_HOVER_TEXT

    style.page_button.xpadding = 10
    style.page_button.hover_background = Solid(VITA_FOCUS_FILL + "d0")
    style.page_button.selected_idle_background = Solid(VITA_SELECTED_FILL + "f0")
    style.page_button.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "f2")
    style.page_button_text.color = VITA_INK
    style.page_button_text.hover_color = VITA_INK_FOCUS
    style.page_button_text.selected_idle_color = VITA_SELECTED_TEXT
    style.page_button_text.selected_hover_color = VITA_SELECTED_HOVER_TEXT

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

    # Desktop Ren'Py predicts every ShowMenu target reachable from the current
    # navigation screen. On Vita that repeatedly walks the Load screen and its
    # save thumbnails even while opening Preferences or About. These screens
    # are small enough to build on demand, which avoids the recurring pause.
    config.predict_screens = False
    config.predict_file_pages = False

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
    for button_style_name in ("radio_button", "check_button", "mute_all_button"):
        button_style = getattr(style, button_style_name)
        # The stock radio/check glyph rasters are transparent when idle and
        # blue when selected, which vanishes against the active fill. The
        # button fill and high-contrast text now carry the state instead.
        button_style.foreground = None
        button_style.hover_background = Solid(VITA_FOCUS_FILL + "80")
        button_style.selected_idle_background = Solid(VITA_SELECTED_FILL + "80")
        button_style.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "90")
    for text_style_name in ("radio_button_text", "check_button_text", "mute_all_button_text"):
        text_style = getattr(style, text_style_name)
        text_style.color = VITA_INK
        text_style.hover_color = VITA_INK_FOCUS
        text_style.hover_bold = True
        text_style.hover_underline = True
        text_style.selected_idle_color = VITA_SELECTED_TEXT
        text_style.selected_idle_bold = True
        text_style.selected_hover_color = VITA_SELECTED_HOVER_TEXT
        text_style.selected_hover_bold = True
        text_style.selected_hover_underline = True

    # Speaker names previously rendered straight over game art because
    # gui/namebox.png ships fully transparent. Put them on the shared light
    # panel so the dark-blue name always has a predictable background.
    # "namebox" has no underscore, so unlike derived names it is not
    # auto-created; the headless precompile run skips it, the real game
    # always has it registered by screens.rpy.
    try:
        style.namebox.background = Solid(VITA_PANEL + "ea")
    except Exception:
        pass

    # In-game decision buttons were still desktop-sized (22 px grey text,
    # blue-on-blue hover). Give them the same readable state language and
    # sizes as the menus; they float over game art, so their idle fill is
    # nearly opaque.
    style.choice_vbox.spacing = 24
    style.choice_button.xsize = 1000
    style.choice_button.ysize = 78
    style.choice_button.background = Solid("#eef4faf2")
    style.choice_button.hover_background = Solid(VITA_FOCUS_FILL + "ff")
    style.choice_button.selected_idle_background = Solid(VITA_SELECTED_FILL + "ff")
    style.choice_button.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "ff")
    style.choice_button_text.size = 40
    style.choice_button_text.color = "#26303c"
    style.choice_button_text.hover_color = VITA_INK_FOCUS
    style.choice_button_text.selected_idle_color = VITA_SELECTED_TEXT
    style.choice_button_text.selected_hover_color = VITA_SELECTED_HOVER_TEXT
    style.choice_button_text.insensitive_color = "#5f6a77"

    # Save/notify toasts and the skip indicator were 16 px, which shrinks to
    # roughly 9 physical pixels on the Vita display.
    style.notify_text.size = 34
    style.skip_text.size = 34

    # Confirmation prompts are modal on Vita and must remain readable after the
    # 1694x960 canvas is scaled to the physical display.
    style.vita_confirm_frame.xsize = 900
    style.vita_confirm_frame.ysize = 420
    style.vita_confirm_prompt_text.size = 44
    style.vita_confirm_prompt_text.xsize = 780
    style.vita_confirm_button.xsize = 260
    style.vita_confirm_button.ysize = 100
    style.vita_confirm_button.background = Solid("#e5e8edff")
    style.vita_confirm_button.hover_background = Solid(VITA_FOCUS_FILL + "ff")
    style.vita_confirm_button.selected_idle_background = Solid(VITA_SELECTED_FILL + "ff")
    style.vita_confirm_button.selected_hover_background = Solid(VITA_SELECTED_FILL_HOVER + "ff")
    style.vita_confirm_button_text.size = 40
    style.vita_confirm_button_text.color = "#4f5664"
    style.vita_confirm_button_text.hover_color = VITA_INK_FOCUS
    style.vita_confirm_button_text.selected_idle_color = VITA_SELECTED_TEXT
    style.vita_confirm_button_text.selected_hover_color = VITA_SELECTED_HOVER_TEXT
    style.vita_confirm_button_text.outlines = []

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
    style.vita_side_button.hover_background = Solid("#1565c0e6")
    # Toggle buttons on the sidebar (Auto, Skip) show their active state with
    # the shared solid-blue selected fill.
    style.vita_side_button.selected_idle_background = Solid("#0d47a1f0")
    style.vita_side_button.selected_hover_background = Solid("#1565c0f0")
    style.vita_side_button.keyboard_focus = False
    style.vita_side_button_text.size = 35
    style.vita_side_button_text.color = "#ffffff"
    style.vita_side_button_text.hover_color = "#ffffff"
    style.vita_side_button_text.selected_idle_color = "#ffffff"
    style.vita_side_button_text.selected_hover_color = "#ffffff"
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
default persistent.vita_side_buttons = True


# The source navigation screen contains desktop-only Help and a game-specific
# Extra entry whose gallery dependencies are not present in the Vita payload.
# Replace it completely so no hidden action from the compiled screen remains.
screen navigation():
    frame:
        style "vita_navigation_panel"
        xpos gui.navigation_xpos
        xoffset -34
        yalign 0.5

        vbox:
            style_prefix "navigation"
            spacing 10

            if main_menu:
                textbutton "Start" action Start()
            else:
                textbutton "History" action ShowMenu("history") selected renpy.get_screen("history") is not None
                textbutton "Save" action ShowMenu("save") selected renpy.get_screen("save") is not None

            textbutton "Load" action ShowMenu("load") selected renpy.get_screen("load") is not None
            textbutton "Preferences" action ShowMenu("preferences") selected renpy.get_screen("preferences") is not None

            if _in_replay:
                textbutton "End Replay" action EndReplay(confirm=True)
            elif not main_menu:
                textbutton "Main Menu" action MainMenu()

            textbutton "About" action ShowMenu("about") selected renpy.get_screen("about") is not None


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

    if quick_menu and persistent.vita_side_buttons:
        vbox:
            style_prefix "vita_side"
            xpos vita_sidebar_inset
            yalign 0.28
            spacing vita_sidebar_spacing

            textbutton "SELECT\nQ. Save" action QuickSave() keyboard_focus False
            textbutton "L+SELECT\nQ. Load" action QuickLoad() keyboard_focus False

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

                vbox:
                    style_prefix "check"
                    label "Interface"
                    textbutton "Show Side Buttons" action ToggleField(persistent, "vita_side_buttons")

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
