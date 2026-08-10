# Harvis Release Checklist

Use this checklist before creating a GitHub release. The release itself is intentionally manual.

## 1. Sync and environment

- [ ] Pull the latest `main` branch.
- [ ] Confirm the working tree has no unintended local changes.
- [ ] Confirm Python 3.11 or newer is being used.
- [ ] Confirm `.venv` is active or use the virtual-environment Python directly.
- [ ] Install or refresh dependencies with `python -m pip install -r requirements.txt`.

## 2. Automated checks

- [ ] Run the full test suite:

```powershell
python -m pytest
```

- [ ] Confirm there are no syntax or import failures.
- [ ] If any test is skipped or fails because of the local environment, record that clearly in the release notes instead of treating the suite as fully passed.

## 3. Windows runtime smoke test

- [ ] Start Harvis with `python -m harvis`.
- [ ] Confirm a second normal launch reactivates the existing Harvis instance instead of creating a duplicate process.
- [ ] Confirm the startup greeting works in Speaking mode.
- [ ] Confirm Harvis responds without an artificial delay after Gemini Live connects.
- [ ] Confirm Harvis shuts down cleanly from its self-shutdown command.
- [ ] Confirm `START_HARVIS.vbs` launches Harvis without leaving a terminal window visible.
- [ ] Confirm `%APPDATA%\Harvis\harvis.log` receives runtime output when using the VBS launcher.

## 4. Speaking mode

- [ ] Confirm microphone input works.
- [ ] Confirm Gemini voice output works.
- [ ] Confirm the configured voice volume is respected.
- [ ] Confirm the preferred language setting is respected.
- [ ] Confirm the Sphere visualizer reacts to real Gemini audio.
- [ ] Short-click the Sphere and confirm microphone forwarding becomes muted.
- [ ] Confirm the muted Sphere shows the diagonal indicator.
- [ ] Speak while muted and confirm Harvis does not receive the microphone audio.
- [ ] Short-click the Sphere again and confirm microphone forwarding resumes immediately without reconnecting Gemini Live.
- [ ] Drag the Sphere and confirm moving it does not toggle the microphone state.
- [ ] Confirm the Bars visualizer reacts to real Gemini audio.
- [ ] Confirm visualizer previews still work independently.

Preview commands:

```powershell
python -m harvis --visualizer-preview sphere
python -m harvis --visualizer-preview bars
```

## 5. Silent mode

- [ ] Switch Settings > General > Mode to `Silent` and save.
- [ ] Confirm the microphone and speaker streams are not used.
- [ ] Confirm the compact text popup appears.
- [ ] Confirm the popup is transparent, movable, and always on top.
- [ ] Confirm typed commands work without saying Harvis or Jarvis.
- [ ] Confirm visual searches show generic status text such as `Searching...` rather than exposing the target name.
- [ ] Switch back to `Speaking` and confirm the normal live surface returns correctly.

## 6. Desktop tools

Test representative actions without using sensitive or destructive targets:

- [ ] Open an installed application.
- [ ] Close an installed application.
- [ ] Open an HTTP or HTTPS URL.
- [ ] Change master volume.
- [ ] Use a browser action such as opening a new tab.
- [ ] Use a media action if media is available.
- [ ] Scroll a page or document.
- [ ] Type a short Unicode sentence with punctuation.
- [ ] Type a multi-line sequence that uses physical Enter presses correctly.

## 7. Visual interaction

- [ ] Confirm Gemini Vision can locate and click a harmless visible target when cloud vision is available.
- [ ] Confirm the local locator can complete a harmless visual action when Gemini Vision is unavailable or fails.
- [ ] Confirm Harvis performs the final Gemini Vision retry when both the first cloud attempt and local locator miss.
- [ ] Confirm Harvis fails safely instead of clicking randomly when no target reaches the confidence threshold.
- [ ] Confirm sensitive visual actions request explicit confirmation before clicking.

Expected locator order:

```text
Gemini Vision -> Local fallback -> Gemini Vision retry -> safe failure
```

## 8. AI watermark

With Settings > AI > `AI watermark` set to `On`:

- [ ] Ask Harvis to write or draft text and confirm the content begins with `#G6m2i9 `.
- [ ] Ask Harvis to write multiple lines and confirm the marker appears only once at the beginning of the authored content.
- [ ] Perform a search and confirm the query does not receive the marker.
- [ ] Enter or open a URL and confirm it does not receive the marker.
- [ ] Perform navigation or browser-field entry and confirm it does not receive the marker.

Then set `AI watermark` to `Off`:

- [ ] Confirm authored text is written without the marker.

## 9. Credentials and settings

- [ ] Confirm Settings > AI shows the Gemini API key as configured without revealing it.
- [ ] Confirm saving an empty API-key field keeps the existing key.
- [ ] Confirm replacing the API key restarts the assistant cleanly.
- [ ] Confirm the Gemini API key does not appear in `settings.json`.
- [ ] Confirm all expected settings persist after restarting Harvis.

## 10. Repository review

- [ ] Review `README.md` for accuracy.
- [ ] Review `RELEASE_NOTES.md` and replace `vX.Y.Z` with the chosen release version.
- [ ] Decide whether to add a project license before public distribution.
- [ ] Confirm no API keys, secrets, logs, virtual environments, build folders, or personal temporary files are tracked.
- [ ] Confirm all committed repository text is in English.

## 11. GitHub release

- [ ] Choose the final semantic version and tag.
- [ ] Use the updated `RELEASE_NOTES.md` as the basis for the GitHub release description.
- [ ] Mark the release as a pre-release if it is still considered experimental.
- [ ] Publish only after the runtime smoke tests above are complete.

## Current packaging note

The repository currently ships as Python source with helper launch scripts. It does not yet include a signed executable or installer, so the release should not claim that an installer is included unless one is added and tested first.
