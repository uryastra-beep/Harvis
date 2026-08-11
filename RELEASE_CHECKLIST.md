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
- [ ] Leave Harvis running through the previous idle-disconnect window and confirm it remains usable afterward.
- [ ] If Gemini Live rotates or drops the connection, confirm Harvis reconnects automatically instead of requiring a process restart.
- [ ] Confirm a reconnect does not replay the normal startup greeting.
- [ ] Confirm Harvis shuts down cleanly from its self-shutdown command.
- [ ] Confirm `START_HARVIS.vbs` launches Harvis without leaving a terminal window visible.
- [ ] Confirm `%APPDATA%\Harvis\harvis.log` receives runtime output when using the VBS launcher.

## 4. Speaking mode

- [ ] Confirm microphone input works.
- [ ] Confirm Gemini voice output works.
- [ ] Confirm the configured voice volume is respected.
- [ ] Confirm the preferred language setting is respected.
- [ ] Confirm the Sphere visualizer reacts to real Gemini audio.
- [ ] Ask Harvis a normal question and confirm the Sphere smoothly morphs into the rotating loading indicator while the request is being processed.
- [ ] Confirm the normal audio-reactive Sphere returns when Harvis begins responding.
- [ ] Ask Harvis to visually find a harmless target and confirm the loading indicator is active while the locator is searching.
- [ ] Confirm the Sphere returns after the visual search succeeds, fails safely, or requests confirmation.
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
- [ ] Confirm a queued typed command can still be sent after a transient Live reconnect.
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

## 7. Mobile remote control

Use a phone or tablet connected to the same trusted local network as the Harvis computer:

- [ ] Confirm mobile remote control is `Off` by default for an existing or fresh settings file.
- [ ] Enable Settings > Advanced > `Remote control`, save settings, and confirm a phone URL and six-digit pairing code appear.
- [ ] Open the phone URL and confirm the responsive Harvis Remote page loads.
- [ ] Confirm an incorrect pairing code is rejected.
- [ ] Pair with the displayed code and confirm authenticated status polling begins.
- [ ] Send a harmless text command from the phone while Harvis is in Speaking mode and confirm the same Gemini Live assistant handles it.
- [ ] Switch to Silent mode and confirm a paired phone command still reaches Harvis.
- [ ] Confirm the mobile page displays the latest Harvis status and response transcript.
- [ ] In Speaking mode, mute and unmute the microphone from the phone and confirm both actual microphone forwarding and the Sphere indicator stay in sync.
- [ ] Confirm the microphone control is unavailable or rejected in Silent mode.
- [ ] Change the configured remote port and confirm the server restarts on the new port with a new pairing code and browser token.
- [ ] Restart Harvis and confirm the previous browser token no longer authorizes requests until the phone pairs again.
- [ ] Confirm disabling remote control stops the local server.
- [ ] Confirm no router port forwarding is required and do not expose the remote-control port to the public Internet.

## 8. Multi-step task orchestration

Use harmless deterministic workflows for these checks:

- [ ] Give Harvis one long instruction containing at least three ordered computer actions and confirm it can execute the sequence as one task plan.
- [ ] Confirm actions run in the same order requested by the user.
- [ ] Confirm a plan with more than two steps performs screen-readiness checks between UI-changing actions.
- [ ] Confirm a long plan waits while a newly opened application or page is still visually changing instead of immediately running the next UI-dependent action.
- [ ] Add a `ready_target` to a non-click step and confirm Harvis does not run that step until the requested visible field, button, icon, text label, or UI state is found.
- [ ] Confirm a `vision_click` step automatically waits for its own target before attempting the click even when `ready_target` is omitted.
- [ ] Confirm a missing readiness target stops the remaining workflow before the dependent step runs.
- [ ] Confirm a screen that never becomes stable stops the remaining workflow instead of continuing blindly.
- [ ] Confirm a one-step or two-step action plan does not add the long-workflow screen-readiness checks.
- [ ] Include a short explicit wait between two actions and confirm the workflow resumes afterward.
- [ ] Confirm a plan can combine representative actions such as opening an app, typing text, pressing Enter, and performing another approved local action.
- [ ] Confirm an invalid plan is rejected before its first action runs.
- [ ] Confirm a plan stops if a step raises an error instead of continuing into later actions.
- [ ] Confirm a missing or low-confidence visual target stops the remaining plan safely.
- [ ] Confirm a sensitive visual action pauses the plan for explicit confirmation instead of continuing automatically.
- [ ] Confirm Harvis self-shutdown cannot be embedded inside an action plan.
- [ ] Confirm a workflow that depends on an unknown newly revealed screen state can fall back to individual tools after the deterministic prefix instead of guessing the rest.

## 9. Visual interaction

- [ ] Confirm Gemini Vision can locate and click a harmless visible target when cloud vision is available.
- [ ] Confirm the local locator can complete a harmless visual action when Gemini Vision is unavailable or fails.
- [ ] Confirm Harvis performs the final Gemini Vision retry when both the first cloud attempt and local locator miss.
- [ ] Confirm Harvis fails safely instead of clicking randomly when no target reaches the confidence threshold.
- [ ] Confirm sensitive visual actions request explicit confirmation before clicking.

Expected locator order:

```text
Gemini Vision -> Local fallback -> Gemini Vision retry -> safe failure
```

## 10. AI watermark

With Settings > AI > `AI watermark` set to `On`:

- [ ] Ask Harvis to write or draft text and confirm the content begins with `#G6m2i9 `.
- [ ] Ask Harvis to write multiple lines and confirm the marker appears only once at the beginning of the authored content.
- [ ] Perform a search and confirm the query does not receive the marker.
- [ ] Enter or open a URL and confirm it does not receive the marker.
- [ ] Perform navigation or browser-field entry and confirm it does not receive the marker.
- [ ] Send an authored-writing request from the paired mobile page and confirm it follows the same watermark behavior.

Then set `AI watermark` to `Off`:

- [ ] Confirm authored text is written without the marker.

## 11. Credentials and settings

- [ ] Confirm Settings > AI shows the Gemini API key as configured without revealing it.
- [ ] Confirm saving an empty API-key field keeps the existing key.
- [ ] Confirm replacing the API key restarts the assistant cleanly.
- [ ] Confirm the Gemini API key does not appear in `settings.json`.
- [ ] Confirm mobile remote enabled state and LAN port persist after restarting Harvis.
- [ ] Confirm the remote pairing code and browser token are not written to `settings.json`.
- [ ] Confirm all expected settings persist after restarting Harvis.

## 12. Repository review

- [ ] Review `README.md` for accuracy.
- [ ] Review `RELEASE_NOTES.md` and replace `vX.Y.Z` with the chosen release version.
- [ ] Decide whether to add a project license before public distribution.
- [ ] Confirm no API keys, secrets, logs, virtual environments, build folders, or personal temporary files are tracked.
- [ ] Confirm all committed repository text is in English.

## 13. GitHub release

- [ ] Choose the final semantic version and tag.
- [ ] Use the updated `RELEASE_NOTES.md` as the basis for the GitHub release description.
- [ ] Mark the release as a pre-release if it is still considered experimental.
- [ ] Publish only after the runtime smoke tests above are complete.

## Current packaging note

The repository currently ships as Python source with helper launch scripts. It does not yet include a signed executable or installer, so the release should not claim that an installer is included unless one is added and tested first.
