# PAIOS Android Build Guide

How to build, run, and ship the Android version of PAIOS using
Flutter. The Flutter client already exists in this repository at
`frontend/mobile/` (the *PAIOS Mobile Companion*, Milestone 15) — this
guide takes it from source to a Play-Store-ready app bundle.

---

## 1. What the Android app is

The phone is a **remote client**. All intelligence — the Scheduler,
Decision Engine, Learning Engine, AI assistant — runs in PAIOS Core
Services on the desktop. The Flutter app talks to the same REST API the
desktop GUI uses and stores no domain state of its own (only
preferences, a cached dashboard, and notification history).

```
Windows PAIOS Desktop  (PAIOS.exe: tray, desktop GUI)
        |
        v
PAIOS Core Services    (daemon + REST API, http://<host>:8765)
        |
        v
Flutter Android Client (frontend/mobile — this guide)
```

## 2. Required tools

| Tool | Version | Purpose |
|------|---------|---------|
| Flutter SDK | 3.22+ (Dart >= 3.4) | build system + framework |
| Android Studio | latest stable | Android SDK manager, emulator, signing UI |
| Android SDK | API 34 (min SDK 21) | platform + build tools |
| JDK | 17 (bundled with recent Android Studio) | Gradle builds |

Verify the toolchain:

```bash
flutter doctor
```

Every line must be a check mark before continuing (`flutter doctor
--android-licenses` accepts the SDK licenses).

## 3. Development setup

```bash
# 1. Clone the repository
git clone https://github.com/adsecurto-boop/PAIOS.git
cd PAIOS/frontend/mobile

# 2. Generate the Android platform scaffolding (one time — it is not
#    tracked in git; lib/, test/ and pubspec.yaml are)
flutter create --platforms=android --project-name paios_mobile .

# 3. Install dependencies
flutter pub get

# 4. Run the test suite
flutter test
```

**Cleartext HTTP (required):** the REST API is plain `http` on the LAN,
so add to the generated
`android/app/src/main/AndroidManifest.xml` `<application>` tag:

```xml
<application android:usesCleartextTraffic="true" ...>
```

(or ship a `networkSecurityConfig` that allows cleartext for private
address ranges only — the stricter option).

**Point the app at a backend:** on the desktop, start the API on a
LAN-reachable interface:

```bash
python -m paios.api --host 0.0.0.0
```

Then in the app: **Settings → Backend URL** →
`http://<laptop-LAN-IP>:8765`. Allow TCP 8765 through the Windows
firewall for private networks.

Run on a device/emulator:

```bash
flutter run
```

## 4. Architecture: how the app talks to PAIOS

The client supports exactly one transport today, with three documented
growth options:

1. **Local REST API (current).** `lib/services/api_client.dart` calls
   the desktop's HTTP API (`/status`, `/events`, `/plan`, `/inbox`,
   `/assistant/*`, …). Works on the same Wi-Fi network. Zero cloud,
   zero accounts — matches the desktop product's privacy posture.
2. **REST over a tunnel.** The same client works across networks
   through any user-managed tunnel (Tailscale, WireGuard, SSH port
   forward). No app changes needed — just a different Backend URL.
   This is the recommended "away from home" option.
3. **WebSocket push (future).** The API is poll-based today
   (`refresh_seconds`). A `/ws` endpoint on the backend would let the
   phone receive plan/notification changes instead of polling; the
   `AppState` service is already a single subscription point where a
   socket could replace the timer.
4. **Cloud synchronization (future, opt-in).** A relay service holding
   end-to-end-encrypted event snapshots would allow offline phones to
   catch up. This is deliberately NOT built: it introduces accounts and
   server costs, and the current product promise is local-first.

Decision guidance: stay REST-only until a real user need for push
latency or offline write appears; every step down the list adds
operational surface.

## 5. Building APKs

Debug (development, larger, debuggable):

```bash
flutter build apk --debug
```

Release (optimized, requires signing for distribution):

```bash
flutter build apk --release
```

Output: `build/app/outputs/flutter-apk/app-release.apk`. Sideload with
`adb install app-release.apk`.

For device-specific smaller APKs:

```bash
flutter build apk --release --split-per-abi
```

## 6. Play Store preparation

### 6.1 Create the upload keystore (once, keep it forever)

```bash
keytool -genkey -v -keystore %USERPROFILE%\paios-upload.jks ^
    -keyalg RSA -keysize 2048 -validity 10000 -alias paios
```

Back this file and its passwords up — losing the upload key locks you
out of updating the app.

### 6.2 Wire signing into Gradle

`android/key.properties` (never commit this file):

```properties
storePassword=<password>
keyPassword=<password>
keyAlias=paios
storeFile=C:/Users/<you>/paios-upload.jks
```

In `android/app/build.gradle`, load `key.properties` and set the
`release` signing config to it (the standard Flutter signing recipe
from the Flutter docs applies unchanged).

### 6.3 Version management

The Play Store version comes from `pubspec.yaml`:

```yaml
version: 1.0.0+1    # <versionName>+<versionCode>
```

Rules: bump `+N` (the build number) on EVERY upload; bump the semantic
part when the desktop product version jumps. Keep the mobile version
aligned with the backend versions it was tested against and state the
supported API version in the Play listing notes.

### 6.4 Build the App Bundle (what Play accepts)

```bash
flutter build appbundle
```

Output: `build/app/outputs/bundle/release/app-release.aab`. Upload in
Play Console → Production (or an internal/closed testing track first —
recommended for the first release).

### 6.5 Store listing checklist

- App name: PAIOS Mobile Companion
- Category: Productivity
- Data safety form: no data collected, no data shared (the app talks
  only to the user's own machine)
- Screenshots: dashboard, timeline, planning, settings (dark theme)
- Privacy policy URL (required by Play even when no data is collected)

## 7. Release flow summary

```
flutter test                      # green suite
flutter build appbundle           # signed .aab
Play Console: internal testing -> closed testing -> production
Tag the repo: mobile-v<version>
```

## 8. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| App shows the offline banner | Backend not reachable: API must run with `--host 0.0.0.0`, firewall must allow 8765, phone must be on the same network |
| `Cleartext HTTP traffic not permitted` | Missing `usesCleartextTraffic` (section 3) |
| `flutter create` refuses to run | Run it inside `frontend/mobile`, with the directory name intact (`paios_mobile` is set by `--project-name`) |
| Gradle JDK errors | Point Android Studio's Gradle JDK at the bundled JDK 17 |
| Signing errors on `appbundle` | `key.properties` path or passwords wrong; verify with `keytool -list -keystore paios-upload.jks` |
