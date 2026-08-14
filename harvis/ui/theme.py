PRIMARY = "#00072B"
SECONDARY = "#85B1FF"
TERTIARY = "#53EEFC"
TEXT_PRIMARY = "#F4F7FF"
TEXT_MUTED = "#AAB8D6"

# Glass surfaces preserve the official palette while adding translucency and depth.
SURFACE = "rgba(6, 17, 61, 178)"
SURFACE_HOVER = "rgba(133, 177, 255, 22)"
BORDER = "rgba(83, 238, 252, 150)"
BORDER_SOFT = "rgba(83, 238, 252, 88)"
GLASS_HIGHLIGHT = "rgba(255, 255, 255, 34)"
CONTROL_SURFACE = "rgba(255, 255, 255, 16)"
CONTROL_SURFACE_HOVER = "rgba(255, 255, 255, 25)"
SLIDER_TRACK = "rgba(30, 50, 109, 190)"


APP_STYLESHEET = f"""
QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 10pt;
}}

QMainWindow {{
    background-color: {PRIMARY};
}}

QLabel#titleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 23pt;
    font-weight: 700;
}}

QLabel#sectionTitle {{
    color: {SECONDARY};
    font-size: 16pt;
    font-weight: 700;
}}

QLabel#mutedLabel {{
    color: {TEXT_MUTED};
}}

QWidget#animatedSidebar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 22px;
}}

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: 20px;
    margin-top: 13px;
    padding: 18px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 15px;
    padding: 1px 8px;
    color: {SECONDARY};
    background-color: rgba(0, 7, 43, 150);
    border-radius: 7px;
}}

QPushButton {{
    background-color: rgba(133, 177, 255, 232);
    color: {PRIMARY};
    border: 1px solid {GLASS_HIGHLIGHT};
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: rgba(158, 196, 255, 242);
    border-color: rgba(255, 255, 255, 66);
}}

QPushButton:pressed {{
    background-color: rgba(112, 166, 255, 230);
    padding-top: 11px;
    padding-bottom: 9px;
}}

QComboBox,
QLineEdit,
QSpinBox {{
    background-color: {CONTROL_SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    min-height: 34px;
    padding: 0 10px;
    selection-background-color: {SECONDARY};
    selection-color: {PRIMARY};
}}

QScrollArea#settingsPageScroll {{
    background-color: transparent;
    border: none;
}}

QComboBox:hover,
QLineEdit:hover,
QSpinBox:hover {{
    background-color: {CONTROL_SURFACE_HOVER};
    border-color: {BORDER};
}}

QComboBox:focus,
QLineEdit:focus,
QSpinBox:focus {{
    background-color: rgba(255, 255, 255, 22);
    border: 1px solid {TERTIARY};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox QAbstractItemView {{
    background-color: rgba(6, 17, 61, 242);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
    selection-background-color: rgba(133, 177, 255, 220);
    selection-color: {PRIMARY};
    outline: none;
}}

QCheckBox {{
    spacing: 10px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 1px solid {BORDER};
    border-radius: 7px;
    background-color: {CONTROL_SURFACE};
}}

QCheckBox::indicator:hover {{
    background-color: {CONTROL_SURFACE_HOVER};
    border-color: {TERTIARY};
}}

QCheckBox::indicator:checked {{
    background-color: {SECONDARY};
    border-color: rgba(255, 255, 255, 96);
}}

QSlider {{
    background-color: transparent;
    padding: 5px 0;
}}

QSlider::groove:horizontal {{
    height: 7px;
    background: {SLIDER_TRACK};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {SECONDARY};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
    background: {TERTIARY};
    border: 2px solid rgba(255, 255, 255, 190);
}}

QSlider::handle:horizontal:hover {{
    background: rgba(111, 246, 255, 255);
    border: 2px solid rgba(255, 255, 255, 230);
}}

QStatusBar {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
}}

QToolTip {{
    background-color: rgba(6, 17, 61, 238);
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    padding: 6px 9px;
}}
"""


def build_app_stylesheet(
    scale_percent: int = 100,
    *,
    high_contrast: bool = False,
) -> str:
    """Return the application stylesheet with accessibility overrides."""

    scale = max(80, min(180, int(scale_percent)))
    point_size = max(8.0, min(18.0, 10.0 * scale / 100.0))
    stylesheet = APP_STYLESHEET + f"""
QWidget {{
    font-size: {point_size:.1f}pt;
}}

QPushButton:focus,
QCheckBox:focus,
QComboBox:focus,
QLineEdit:focus,
QSpinBox:focus,
QSlider:focus {{
    outline: none;
    border: 2px solid {TERTIARY};
}}
"""
    if high_contrast:
        stylesheet += f"""
QWidget {{
    color: #FFFFFF;
}}
QGroupBox,
QWidget#animatedSidebar,
QComboBox,
QLineEdit,
QSpinBox {{
    border-color: #FFFFFF;
}}
QLabel#mutedLabel {{
    color: #DDE7FF;
}}
QCheckBox::indicator {{
    border: 2px solid #FFFFFF;
}}
QPushButton:focus,
QCheckBox:focus,
QComboBox:focus,
QLineEdit:focus,
QSpinBox:focus,
QSlider:focus {{
    border: 3px solid {TERTIARY};
}}
"""
    return stylesheet
