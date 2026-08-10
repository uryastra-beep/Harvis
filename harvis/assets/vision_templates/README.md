# Local Vision Templates

Harvis can use classical OpenCV template matching as one signal in the local visual locator.

Place small reference images in this directory when a stable icon or UI mark should be recognized locally. Supported formats are PNG, JPG, JPEG, and BMP.

Use a descriptive filename that matches how the user normally names the target, for example:

- `github.png`
- `whatsapp.png`
- `spotify.png`
- `send_button.png`

The matcher tries several nearby scales and combines template evidence with accessibility labels, control roles, colors, and geometry. A template match is never required when another local method is already confident.

Keep templates tightly cropped around the visual element, avoid personal information, and do not store full screenshots here.
