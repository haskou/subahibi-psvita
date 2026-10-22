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

    # The build pre-scales every image to the Vita's 544/960 display scale and
    # records its original size, which is the size the BGI layout code expects.
    # The table lives on the function, outside the store, so it is neither
    # saved nor rolled back, and python_dict is the builtin, non-revertable dict.
    def vita_image_size(name):
        sizes = vita_image_size.sizes
        if sizes is None:
            stream = renpy.file("vita_image_sizes.txt")
            try:
                lines = stream.read().decode("utf-8").splitlines()
            finally:
                stream.close()
            sizes = python_dict()
            for line in lines:
                image_name, width, height = line.split("\t")
                sizes[image_name] = (int(width), int(height))
            vita_image_size.sizes = sizes
        return sizes[name.lower()]

    vita_image_size.sizes = None

    def vita_lazy_image(what):
        if not isinstance(what, tuple):
            return None

        image_name = " ".join(what).lower()
        filename = "images/{}.webp".format(image_name)

        if renpy.loadable(filename):
            displayable = Transform(
                renpy.display.im.Image(filename), size=vita_image_size(image_name)
            )
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
    import threading

    # --- Vita menu palette (white / blue) -----------------------------------
    # The menus keep the desktop light template's look: white overlays, the
    # #0099ff rule and markers, and gui.hover_color text. One state language
    # is shared by every menu surface:
    #   idle      dark ink text, no fill
    #   focus     light-blue fill inside a dark-blue frame; the item the cross
    #             button activates
    #   selected  dark-blue bold text plus a blue marker (current screen,
    #             active option)
    # Focus never changes text weight, so moving the cursor never reflows a
    # menu.
    VITA_ACCENT = "#0099ff"
    VITA_INK = "#3d4654"
    VITA_INK_FOCUS = "#003366"
    VITA_FOCUS_FILL = "#d6edff"
    VITA_FOCUS_RING = "#0066cc"
    VITA_SELECTED_FILL = "#8fd3f4"
    VITA_SELECTED_FILL_HOVER = "#72c3ed"
    VITA_SELECTED_TEXT = "#004b80"
    VITA_SELECTED_HOVER_TEXT = "#002c5c"
    VITA_PANEL = "#f7f9fb"
    # The stock 90% white overlay composited over the game-menu background.
    VITA_MENU_SURFACE = "#eff1f2"

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

    # Every text/background pair used by the menu styles must pass WCAG AA
    # (4.5:1), and the focus frame must reach the 3:1 non-text minimum against
    # everything it borders. This runs at every boot, so a future colour tweak
    # that breaks legibility fails loudly instead of shipping unreadable menus.
    for vita_fg, vita_bg, vita_minimum in (
        (VITA_INK, VITA_MENU_SURFACE, 4.5),
        (VITA_INK, VITA_PANEL, 4.5),
        (VITA_INK_FOCUS, VITA_FOCUS_FILL, 4.5),
        (VITA_INK_FOCUS, VITA_MENU_SURFACE, 4.5),
        (VITA_INK_FOCUS, VITA_PANEL, 4.5),
        ("#4f5664", "#e5e8ed", 4.5),
        (VITA_SELECTED_TEXT, VITA_SELECTED_FILL, 4.5),
        (VITA_SELECTED_HOVER_TEXT, VITA_SELECTED_FILL_HOVER, 4.5),
        ("#26303c", "#eef4fa", 4.5),
        (VITA_FOCUS_RING, VITA_MENU_SURFACE, 3.0),
        (VITA_FOCUS_RING, VITA_FOCUS_FILL, 3.0),
        (VITA_FOCUS_RING, "#99d6ff", 3.0),
    ):
        if vita_contrast(vita_fg, vita_bg) < vita_minimum:
            raise Exception(
                "Vita UI palette fails WCAG contrast: {} on {}".format(
                    vita_fg, vita_bg
                )
            )

    def vita_layers(*children):
        """Stack displayables in a Fixed that fills the area it is given."""
        rv = Fixed()
        for child in children:
            rv.add(child)
        return rv

    def vita_focus_frame(fill=VITA_FOCUS_FILL, inner=None):
        """The focus cursor: a fill, an optional inner layer, a 4 px frame."""
        edge = 4
        layers = [Solid(fill)]
        if inner is not None:
            layers.append(inner)
        layers.extend((
            Solid(VITA_FOCUS_RING, ysize=edge),
            Solid(VITA_FOCUS_RING, ysize=edge, yalign=1.0),
            Solid(VITA_FOCUS_RING, xsize=edge),
            Solid(VITA_FOCUS_RING, xsize=edge, xalign=1.0),
        ))
        return vita_layers(*layers)

    def vita_selected_marker():
        """The stock radio marker: a 6x36 accent bar at the left edge."""
        return vita_layers(
            Solid(VITA_ACCENT, xpos=4, xsize=6, ysize=36, yalign=0.5)
        )

    def vita_page_marker():
        """Selected save page: an accent underline."""
        return vita_layers(Solid(VITA_ACCENT, ysize=4, yalign=1.0))

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

    # The game menu covers the whole game rectangle with an opaque background,
    # so the scene underneath only costs render time. Hide every game layer
    # while a menu is open; Ren'Py restores them when the menu closes.
    config.menu_clear_layers = ["master", "f30x", "f39x", "transient"]

    # The stock game-menu background is a uniform #5f727f raster whose decode
    # was the largest single cost of opening the menu with START.
    gui.game_menu_background = Solid("#5f727f")

    # The build stores the main-menu art as a 725x544 lossy WebP, the size the
    # Vita shows it at. vita_warm_main_menu() decodes it during the splash.
    VITA_MAIN_MENU_ART = "gui/main_menu.webp"
    gui.main_menu_background = Transform(VITA_MAIN_MENU_ART, size=(1280, 960))

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

    # Menu screens stay inside the game rectangle, so clipping the screens
    # layer there only adds a render pass. Gameplay keeps clipping, because
    # BGI scripts may move screen content past the rectangle.
    def vita_menu_clipping():
        properties = renpy.display.interface.layer_properties.get("screens")
        if properties is not None:
            properties["clipping"] = not renpy.context()._menu

    config.start_interact_callbacks.append(vita_menu_clipping)

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

    # Cross, circle or START skip the rest of the maker logos and warnings
    # (makerlogo.rpy). The splash is a chain of BGI pauses and dissolves, so a
    # plain dismiss only ends the current step. Ren'Py's fast skip turns every
    # remaining pause and transition into a no-op instead. The splash runs
    # inside 00start.rpy's "call _splashscreen from _call_splashscreen_1", and
    # that return site stays on the return stack exactly while it plays.
    # The press must not map to dismiss: SayBehavior treats a dismiss while
    # skipping as "stop skipping". Unmapped, the event still reaches the
    # current SayBehavior, which ends the running pause or dissolve after
    # config.skip_delay because skipping is now "fast".
    VITA_SPLASH_SKIP_EVENTS = ("pad_a_press", "pad_b_press", "pad_start_press")

    def vita_splash_active():
        return "_call_splashscreen_1" in renpy.get_return_stack()

    # Ren'Py's image prediction never reached the main menu on the Vita. Its
    # first frame decoded the background on the main thread while the audio
    # thread indexed the deferred audio archives for the menu music
    # (tools/patch_vita_runtime.py). Both hold the interpreter lock most of the
    # time, so each slowed the other: a 747 ms decode inside a 1.26 s frame,
    # then a 2.8 s lookup before the music started. A daemon thread does both
    # jobs ahead of time, during the first splash pause of at least
    # VITA_WARMUP_PAUSE_MS (the warning screen), so they compete with neither
    # a dissolve nor the menu. preload_texture() is the call Ren'Py's own
    # preload thread makes; the GL upload still happens on the main thread.
    VITA_WARMUP_PAUSE_MS = 5000

    # A plain list, bound at init and never rebound, so neither rollback nor
    # saves record it.
    vita_warmup_started = python_list()

    def vita_warm_main_menu():
        renpy.display.im.cache.preload_texture(renpy.display.im.Image(VITA_MAIN_MENU_ART))

        # Only the Vita runtime defers the audio archives. If the menu music
        # starts first, its lookup mounts them and this call returns at once.
        if getattr(renpy.loader, "lazy_archives_pending", None):
            renpy.loader.mount_lazy_archives()

    # bgi_f_110 starts by popping the pause length, in milliseconds, from the
    # top of bgi_stack. Fast skip turns the pause into a no-op, so a skipped
    # splash leaves both jobs to the main menu, as before.
    def vita_maybe_start_warmup(name):
        if (name != "bgi_f_110" or vita_warmup_started or config.skipping
                or not vita_splash_active() or not bgi_stack
                or bgi_stack[-1] < VITA_WARMUP_PAUSE_MS):
            return

        vita_warmup_started.append(True)
        thread = threading.Thread(target=vita_warm_main_menu, name="vita_warmup")
        thread.daemon = True
        thread.start()

    # _invoke_main_menu is the first label reached after the splash returns.
    # Fast skip has no meaning in the main menu, so it must not outlive it.
    def vita_label_callback(name, abnormal):
        vita_maybe_start_warmup(name)

        if name == "_invoke_main_menu" and config.skipping == "fast":
            config.skipping = None

    config.label_callback = vita_label_callback

    # Directional controller events may only move focus while a menu or a
    # choice screen is active. This matters after suspend/resume, when SDL can
    # deliver a stale stick/D-pad repeat that would otherwise focus one of the
    # touch-only sidebar buttons. D-pad Down advances dialogue, but its repeats
    # do not, so one press always advances exactly one interaction.
    def vita_map_pad_event(event_name):
        if event_name in VITA_SPLASH_SKIP_EVENTS and vita_splash_active():
            config.skipping = "fast"
            return ()

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

    # Stock Ren'Py only applies default_focus on the first interaction of a
    # screen, and drops focus whenever a menu switches screens because no
    # widget keeps its focus name. With the D-pad that left nothing focused,
    # so the first press jumped to whichever widget happened to be listed
    # first. While a menu is driven by the D-pad, re-apply default_focus after
    # every restart: the cursor stays on the entry of the open screen.
    vita_focus_before_interact = renpy.display.focus.before_interact

    def vita_before_interact(roots):
        interface = renpy.display.interface
        keyboard = (
            renpy.display.focus.pending_focus_type == "keyboard" and
            renpy.context()._menu
        )
        start_interact = interface.start_interact
        if keyboard:
            interface.start_interact = True
        try:
            return vita_focus_before_interact(roots)
        finally:
            interface.start_interact = start_interact

    renpy.display.focus.before_interact = vita_before_interact

    # With nothing focused (for example after touch input), the first D-pad
    # press lands on the screen's default_focus widget instead of the first
    # widget in display order.
    vita_focus_nearest = renpy.display.focus.focus_nearest

    def vita_focus_nearest_default(*args):
        focus = renpy.display.focus
        if focus.get_focused() is None:
            defaults = [
                f for f in focus.focus_list
                if f.widget.default and f.widget.style.keyboard_focus
            ]
            if defaults:
                focus.pending_focus_type = "keyboard"
                return focus.change_focus(
                    max(defaults, key=lambda f: f.widget.default)
                )
        return vita_focus_nearest(*args)

    renpy.display.focus.focus_nearest = vita_focus_nearest_default

    # Stock bars must be grabbed with cross before the D-pad changes them,
    # and nothing on screen says so. A focused bar now moves one step per
    # press along its axis (left/right on sliders, up/down on scrollbars);
    # the grab path still works for touch.
    vita_bar_event = renpy.display.behavior.Bar.event

    def vita_bar_event_direct(self, ev, x, y, st):
        if (
            self.focusable and not self.hidden and self.is_focused() and
            renpy.display.focus.get_grab() is not self
        ):
            map_event = renpy.display.behavior.map_event
            vertical = self.style.bar_vertical
            if map_event(ev, "bar_up" if vertical else "bar_left"):
                step = -self.adjustment.step
            elif map_event(ev, "bar_down" if vertical else "bar_right"):
                step = self.adjustment.step
            else:
                step = 0

            if step:
                adjustment = self.adjustment
                if self.style.bar_invert ^ vertical:
                    step = -step
                value = min(max(adjustment.value + step, 0), adjustment.range)
                if isinstance(adjustment.range, int):
                    value = int(value)
                value = adjustment.round_value(value, release=True)
                if value != adjustment.value:
                    rv = adjustment.change(value)
                    if rv is not None:
                        return rv
                raise renpy.display.core.IgnoreEvent()

        return vita_bar_event(self, ev, x, y, st)

    renpy.display.behavior.Bar.event = vita_bar_event_direct

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

    # gui.init() enables config.defer_styles, so every style statement (the
    # stock ones in screens.rpy included) runs after all init code and beats
    # any style.X.prop assignment made in init python: a later properties
    # block wins, prefixed or not. The menu styles are therefore added from a
    # change_language callback, which runs after the deferred statements at
    # startup and again after every style restore (gui.rebuild included).
    # They are not style statements because each new statement shifts the
    # global node serials that existing saves depend on (docs/BUILDING.md).
    #
    # One focus language: the focused widget gets a light fill inside a 4 px
    # dark blue frame; the selected entry keeps the stock #0099ff marker. The
    # two combine, so the D-pad cursor is never confused with the selection.
    def vita_menu_styles():
        def restyle(name, parent=None, **properties):
            target = renpy.style.get_or_create_style(name)
            if parent is not None:
                target.set_parent(parent)
            target.add_properties(properties)

        restyle(
            "vita_navigation_panel", "empty",
            xsize=286, xpadding=10, ypadding=14,
            background=Solid("#f7f9fbb8"),
        )
        restyle(
            "navigation_button",
            xsize=260, ysize=58, xpadding=18, ypadding=5,
            background=None, hover_background=vita_focus_frame(),
            foreground=None, selected_foreground=vita_selected_marker(),
        )
        restyle(
            "navigation_button_text",
            font=gui.interface_text_font, size=38, outlines=[],
            color=VITA_INK, hover_color=VITA_INK_FOCUS,
            selected_color=VITA_INK_FOCUS, selected_bold=True,
            insensitive_color="#64707f",
        )
        restyle(
            "main_menu_frame",
            background=vita_layers(
                Solid("#ffffffe5", xsize=277),
                Solid(VITA_ACCENT, xpos=277, xsize=3),
            ),
        )
        restyle(
            "game_menu_outer_frame",
            xfill=True, yfill=True,
            background=vita_layers(
                Solid("#ffffffe5"),
                Solid(VITA_ACCENT, xpos=277, ypos=120, xsize=3, ysize=570),
            ),
        )
        # Draggable viewports take focus, and their rect covers the whole
        # content area: focus parked there showed nothing and the D-pad could
        # only leave to the left. Touch dragging does not need keyboard focus.
        restyle("game_menu_viewport", keyboard_focus=False)
        restyle("game_menu_vpgrid", keyboard_focus=False)

        restyle("page_label_text", size=38)
        restyle(
            "page_button",
            xpadding=10, ypadding=6,
            background=None, hover_background=vita_focus_frame(),
            foreground=None, selected_foreground=vita_page_marker(),
        )
        restyle(
            "page_button_text",
            size=36, color=VITA_INK, hover_color=VITA_INK_FOCUS,
            selected_color=VITA_INK_FOCUS, selected_bold=True,
        )
        restyle(
            "slot_button",
            hover_background=vita_focus_frame(
                inner=Frame(
                    "gui/button/slot_hover_background.png",
                    gui.slot_button_borders,
                )
            ),
        )
        restyle(
            "slot_button_text",
            size=34, color=VITA_INK, hover_color=VITA_INK_FOCUS,
            selected_color=VITA_INK_FOCUS,
        )
        restyle("slot_time_text", size=32)
        restyle("slot_name_text", size=34)

        restyle("pref_label_text", size=38)
        for kind in ("radio", "check"):
            restyle(
                kind + "_button",
                left_padding=18, right_padding=14, ypadding=6,
                background=None, hover_background=vita_focus_frame(),
                foreground=None, selected_foreground=vita_selected_marker(),
            )
            restyle(
                kind + "_button_text",
                size=34, color=VITA_INK, hover_color=VITA_INK_FOCUS,
                selected_color=VITA_INK_FOCUS, selected_bold=True,
            )
        restyle("slider_button_text", size=34)
        # Same geometry as the stock slider rasters (#66c1ff bar, #99d6ff when
        # focused, 13 px #0099ff thumb), drawn as solids and taller.
        restyle(
            "slider",
            ysize=32,
            base_bar=Solid("#66c1ff"),
            hover_base_bar=vita_focus_frame("#99d6ff"),
            thumb=Solid(VITA_ACCENT, xsize=13),
            hover_thumb=Solid(VITA_INK_FOCUS, xsize=13),
        )

        restyle("vita_confirm_frame", xsize=900, ysize=420)
        restyle("vita_confirm_prompt_text", size=44, xsize=780)
        # The confirm screen moves `selected` with the D-pad and keeps focus
        # parked on No, so only the selected button shows the focus frame.
        restyle(
            "vita_confirm_button",
            xsize=260, ysize=100,
            background=Solid("#e5e8ed"),
            selected_background=vita_focus_frame(),
        )
        restyle(
            "vita_confirm_button_text",
            size=40, outlines=[], color="#4f5664",
            selected_color=VITA_INK_FOCUS, selected_bold=True,
        )

    config.change_language_callbacks.append(vita_menu_styles)


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
    # The entry of the open menu carries default_focus, so the D-pad cursor
    # starts there. Switching menus only restarts the interaction, where stock
    # Ren'Py skips default_focus; vita_before_interact re-applies it.
    $ vita_current_menu = next(
        (
            name for name in ("history", "save", "load", "preferences", "about")
            if renpy.get_screen(name) is not None
        ),
        None,
    )

    frame:
        style "vita_navigation_panel"
        xpos gui.navigation_xpos
        xoffset -34
        yalign 0.5

        vbox:
            style_prefix "navigation"
            spacing 10

            if main_menu:
                textbutton "Start":
                    action Start()
                    default_focus vita_current_menu is None
            else:
                textbutton "History":
                    action ShowMenu("history")
                    selected vita_current_menu == "history"
                    default_focus vita_current_menu == "history"
                textbutton "Save":
                    action ShowMenu("save")
                    selected vita_current_menu == "save"
                    default_focus vita_current_menu == "save"

            textbutton "Load":
                action ShowMenu("load")
                selected vita_current_menu == "load"
                default_focus vita_current_menu == "load"
            textbutton "Preferences":
                action ShowMenu("preferences")
                selected vita_current_menu == "preferences"
                default_focus vita_current_menu == "preferences"

            if _in_replay:
                textbutton "End Replay" action EndReplay(confirm=True)
            elif not main_menu:
                textbutton "Main Menu" action MainMenu()

            textbutton "About":
                action ShowMenu("about")
                selected vita_current_menu == "about"
                default_focus vita_current_menu == "about"


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

    add Solid("#ffffff99")

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
