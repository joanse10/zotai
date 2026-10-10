"""
Theme definitions, color tokens, and typography for Zotai GUI.
Supports Windows system theme (automatic Light / Dark mode switching).
In CustomTkinter, a ("light_color", "dark_color") tuple adapts to the OS mode automatically.
"""

import customtkinter as ctk


class Theme:
    # Surface backgrounds (Light theme, Dark theme)
    BG_WINDOW = ("#F8FAFC", "#080C14")        # Window: Slate 50 / deep dark
    BG_HEADER = ("#FFFFFF", "#0E1524")        # Header
    BG_PANEL = ("#FFFFFF", "#111A2C")         # Cards and panels
    BG_PANEL_ALT = ("#F1F5F9", "#162238")     # Dividers / secondary containers (Slate 100)
    BG_INPUT = ("#FFFFFF", "#0A0F1A")         # Inputs
    BG_BORDER = ("#E2E8F0", "#1E2D4A")        # Borders (Slate 200)
    BG_BORDER_LIGHT = ("#CBD5E1", "#2A3B5F")  # Hover borders (Slate 300)

    # Text
    TEXT_MAIN = ("#0F172A", "#F8FAFC")        # Primary high-contrast text (Slate 900)
    TEXT_MUTED = ("#64748B", "#94A3B8")       # Secondary muted (Slate 500)
    TEXT_DARK = ("#94A3B8", "#64748B")        # Tertiary

    # Brand Accent (Indigo)
    PRIMARY = ("#4F46E5", "#6366F1")
    PRIMARY_HOVER = ("#4338CA", "#4F46E5")
    PRIMARY_BG = ("#EEF2FF", "#1E1B4B")
    PRIMARY_BG_HOVER = ("#E0E7FF", "#312E81")
    PRIMARY_TEXT = ("#4338CA", "#C7D2FE")

    # Semantic Statuses
    STATUS_SUCCESS = ("#059669", "#10B981")
    STATUS_SUCCESS_BG = ("#ECFDF5", "#064E3B")
    STATUS_SUCCESS_HOVER = ("#D1FAE5", "#065F46")
    STATUS_SUCCESS_TEXT = ("#065F46", "#A7F3D0")

    STATUS_WARNING = ("#D97706", "#F59E0B")
    STATUS_WARNING_BG = ("#FFFBEB", "#78350F")
    STATUS_WARNING_HOVER = ("#FEF3C7", "#92400E")
    STATUS_WARNING_TEXT = ("#92400E", "#FDE68A")

    STATUS_INFO_TEXT = ("#0284C7", "#38BDF8")
    STATUS_INFO_SCAN = ("#7C3AED", "#A855F7")

    STATUS_DANGER = ("#DC2626", "#EF4444")
    STATUS_DANGER_BG = ("#FEF2F2", "#7F1D1D")
    STATUS_DANGER_HOVER = ("#FEE2E2", "#991B1B")
    STATUS_DANGER_TEXT = ("#991B1B", "#FCA5A5")

    @staticmethod
    def font_title():
        return ctk.CTkFont(family="Segoe UI", size=18, weight="bold")

    @staticmethod
    def font_subtitle():
        return ctk.CTkFont(family="Segoe UI", size=12, weight="normal")

    @staticmethod
    def font_section():
        return ctk.CTkFont(family="Segoe UI", size=13, weight="bold")

    @staticmethod
    def font_body():
        return ctk.CTkFont(family="Segoe UI", size=12, weight="normal")

    @staticmethod
    def font_body_bold():
        return ctk.CTkFont(family="Segoe UI", size=12, weight="bold")

    @staticmethod
    def font_caption():
        return ctk.CTkFont(family="Segoe UI", size=10, weight="normal")

    @staticmethod
    def font_caption_bold():
        return ctk.CTkFont(family="Segoe UI", size=10, weight="bold")

    @staticmethod
    def font_mono():
        return ctk.CTkFont(family="Consolas", size=11, weight="normal")


def make_segmented_button_contrast(sb: ctk.CTkSegmentedButton, selected_val=None):
    """
    Ensures high text contrast in CTkSegmentedButton:
    Selected item always has white (#FFFFFF) text on accent background,
    while unselected items have high-contrast Theme.TEXT_MAIN text.
    """
    orig_select = sb._select_button_by_value
    orig_unselect = sb._unselect_button_by_value

    def new_select(val):
        orig_select(val)
        if hasattr(sb, "_buttons_dict") and val in sb._buttons_dict:
            sb._buttons_dict[val].configure(text_color="#FFFFFF")

    def new_unselect(val):
        orig_unselect(val)
        if hasattr(sb, "_buttons_dict") and val in sb._buttons_dict:
            sb._buttons_dict[val].configure(text_color=Theme.TEXT_MAIN)

    sb._select_button_by_value = new_select
    sb._unselect_button_by_value = new_unselect

    target_val = selected_val or (sb.get() if hasattr(sb, "get") else None)
    if hasattr(sb, "_buttons_dict"):
        for k, btn in sb._buttons_dict.items():
            if k == target_val:
                btn.configure(text_color="#FFFFFF")
            else:
                btn.configure(text_color=Theme.TEXT_MAIN)


class ThemedSegmentedButton(ctk.CTkSegmentedButton):
    """
    Segmented button with dynamic contrast highlighting.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        make_segmented_button_contrast(self, self.get())

    def set(self, value: str, from_button_callback: bool = False):
        super().set(value, from_button_callback)
        make_segmented_button_contrast(self, value)
