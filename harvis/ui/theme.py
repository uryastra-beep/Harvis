PRIMARY = "#00072B"
SECONDARY = "#85B1FF"
TERTIARY = "#53EEFC"
TEXT_PRIMARY = "#F4F7FF"
TEXT_MUTED = "#AAB8D6"
SURFACE = "#06113D"
SURFACE_HOVER = "#0B1A50"
BORDER = TERTIARY
SLIDER_TRACK = "#1E326D"


APP_STYLESHEET = f"""
QWidget {{
    background-color: {PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI";
    font-size: 10pt;
}}

QLabel#titleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 22pt;
    font-weight: 700;
}}

QLabel#sectionTitle {{
    color: {SECONDARY};
    font-size: 15pt;
    font-weight: 700;
}}

QLabel#mutedLabel {{
    color: {TEXT_MUTED};
}}

QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 8px;
    outline: none;
}}

QListWidget::item {{
    border-radius: 8px;
    padding: 10px 12px;
    margin: 2px 0;
}}

QListWidget::item:hover {{
    background-color: {SURFACE_HOVER};
}}

QListWidget::item:selected {{
    background-color: {SECONDARY};
    color: {PRIMARY};
    font-weight: 700;
}}

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 10px;
    padding: 14px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {SECONDARY};
}}

QPushButton {{
    background-color: {SECONDARY};
    color: {PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: {TERTIARY};
}}

QComboBox,
QLineEdit,
QSpinBox,
QSlider {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px;
}}

QComboBox:focus,
QLineEdit:focus,
QSpinBox:focus {{
    border: 1px solid {SECONDARY};
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER};
    border-radius: 5px;
    background-color: {SURFACE};
}}

QCheckBox::indicator:checked {{
    background-color: {SECONDARY};
    border-color: {SECONDARY};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {SLIDER_TRACK};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {SECONDARY};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: {TERTIARY};
}}
"""
