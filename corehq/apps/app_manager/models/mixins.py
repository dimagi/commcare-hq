from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    DocumentSchema,
    ListProperty,
    StringProperty,
)


class CommentMixin(DocumentSchema):
    """
    Documentation comment for app builders and maintainers
    """
    comment = StringProperty(default='')

    @property
    def short_comment(self):
        """
        Trim comment to 500 chars (about 100 words)
        """
        return self.comment if len(self.comment) <= 500 else self.comment[:497] + '...'


class CustomIcon(DocumentSchema):
    """
    A custom icon to display next to a module or a form.
    The property "form" identifies what kind of icon this would be, for ex: badge
    One can set either a simple text to display or
    an xpath expression to be evaluated for example count of cases within.
    """

    form = "badge"  # form is always badge
    text = DictProperty(str)
    xpath = StringProperty()

    @property
    def is_text(self):
        return not self.is_xpath

    @property
    def is_xpath(self):
        return bool(self.xpath)


class NavMenuItemMediaMixin(DocumentSchema):
    """
        Language-specific icon and audio.
        Properties are map of lang-code to filepath
    """

    # These were originally DictProperty(JRResourceProperty),
    # but jsonobject<0.9.0 didn't properly support passing in a property to a container type
    # so it was actually wrapping as a StringProperty
    # too late to retroactively apply that validation,
    # so now these are DictProperty(StringProperty)
    media_image = DictProperty(StringProperty)
    media_audio = DictProperty(StringProperty)
    custom_icons = ListProperty(CustomIcon)

    # When set to true, all languages use the specific media from the default language
    use_default_image_for_all = BooleanProperty(default=False)
    use_default_audio_for_all = BooleanProperty(default=False)

    def get_app(self):
        raise NotImplementedError

    def _get_media_by_language(self, media_attr, lang, strict=False, build_profile_id=None):
        """
        Return media-path for given language if one exists, else 1st path in the
        sorted lang->media-path list

        *args:
            media_attr: one of 'media_image' or 'media_audio'
            lang: language code
        **kwargs:
            strict: whether to return None if media-path is not set for lang or
                to return first path in sorted lang->media-path list
            build_profile_id: If this is provided and strict is False, only return
                media in one of the profile's languages
        """
        assert media_attr in ('media_image', 'media_audio')
        app = self.get_app()

        if ((self.use_default_image_for_all and media_attr == 'media_image')
                or (self.use_default_audio_for_all and media_attr == 'media_audio')):
            lang = app.default_language

        media_dict = getattr(self, media_attr)
        if not media_dict:
            return None
        if media_dict.get(lang, ''):
            return media_dict[lang]
        if not strict:
            # if the queried lang key doesn't exist,
            # return the first in the sorted list
            for lang, item in sorted(media_dict.items()):
                if not build_profile_id or lang in app.build_profiles[build_profile_id].langs:
                    return item

    @property
    def default_media_image(self):
        # For older apps that were migrated: just return the first available item
        return self.icon_by_language('')

    @property
    def default_media_audio(self):
        # For older apps that were migrated: just return the first available item
        return self.audio_by_language('')

    def icon_by_language(self, lang, strict=False, build_profile_id=None):
        return self._get_media_by_language('media_image', lang, strict=strict, build_profile_id=build_profile_id)

    def audio_by_language(self, lang, strict=False, build_profile_id=None):
        return self._get_media_by_language('media_audio', lang, strict=strict, build_profile_id=build_profile_id)

    def custom_icon_form_and_text_by_language(self, lang):
        custom_icon = self.custom_icon
        if custom_icon:
            custom_icon_text = custom_icon.text.get(lang, custom_icon.text.get(self.get_app().default_language))
            return custom_icon.form, custom_icon_text
        return None, None

    def set_media(self, media_attr, lang, media_path):
        """
            Caller's responsibility to save doc.
            Currently only called from the view which saves after all Edits
        """
        assert media_attr in ('media_image', 'media_audio')

        media_dict = getattr(self, media_attr) or {}
        old_value = media_dict.get(lang)
        media_dict[lang] = media_path or ''
        setattr(self, media_attr, media_dict)
        # remove the entry from app multimedia mappings if media is being removed now
        # This does not remove the multimedia but just it's reference in mapping
        # Added it here to ensure it's always set instead of getting it only when needed
        app = self.get_app()
        if old_value and not media_path:
            # expire all_media_paths before checking for media path used in Application
            app.all_media.reset_cache(app)
            app.all_media_paths.reset_cache(app)
            if old_value not in app.all_media_paths():
                app.multimedia_map.pop(old_value, None)

    def set_icon(self, lang, icon_path):
        self.set_media('media_image', lang, icon_path)

    def set_audio(self, lang, audio_path):
        self.set_media('media_audio', lang, audio_path)

    def _all_media_paths(self, media_attr, lang=None):
        assert media_attr in ('media_image', 'media_audio')
        media_dict = getattr(self, media_attr) or {}
        valid_media_paths = set()
        for key, value in media_dict.items():
            if value and (lang is None or key == lang):
                valid_media_paths.add(value)
        return valid_media_paths

    def uses_image(self, build_profile_id=None):
        app = self.get_app()
        langs = app.build_profiles[build_profile_id].langs if build_profile_id else app.langs
        return any([self.icon_app_string(lang) for lang in langs])

    def uses_audio(self, build_profile_id=None):
        app = self.get_app()
        langs = app.build_profiles[build_profile_id].langs if build_profile_id else app.langs
        return any([self.audio_app_string(lang) for lang in langs])

    def all_image_paths(self, lang=None):
        return self._all_media_paths('media_image', lang=lang)

    def all_audio_paths(self, lang=None):
        return self._all_media_paths('media_audio', lang=lang)

    def icon_app_string(self, lang, for_default=False, build_profile_id=None):
        """
        Return lang/app_strings.txt translation for given lang
        if a path exists for the lang

        **kwargs:
            for_default: whether app_string is for default/app_strings.txt
        """

        if not for_default and self.icon_by_language(lang, strict=True):
            return self.icon_by_language(lang, strict=True)

        if for_default:
            return self.icon_by_language(lang, strict=False, build_profile_id=build_profile_id)

    def audio_app_string(self, lang, for_default=False, build_profile_id=None):
        """
            see note on self.icon_app_string
        """

        if not for_default and self.audio_by_language(lang, strict=True):
            return self.audio_by_language(lang, strict=True)

        if for_default:
            return self.audio_by_language(lang, strict=False, build_profile_id=build_profile_id)

    @property
    def custom_icon(self):
        if self.custom_icons:
            return self.custom_icons[0]
