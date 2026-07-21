# PAIOS Mobile Companion (Milestone 15)

A Flutter (Material 3, dark-first) remote client for PAIOS. The phone
is only a client: everything comes from the REST API served by the
laptop (`paios serve`); the app never schedules, learns, reasons, or
stores domain state.

## Layout

This directory ships the Dart application and tests only (`lib/`,
`test/`, `pubspec.yaml`). Platform scaffolding is generated, not
tracked — create it once:

```
cd frontend/mobile
flutter create --platforms=android --project-name paios_mobile .
flutter pub get
```

> Android note: to reach the laptop over the LAN, Android needs
> cleartext HTTP permission for the local network (the REST API is
> plain http). Add `android:usesCleartextTraffic="true"` to the
> generated `android/app/src/main/AndroidManifest.xml` `<application>`
> tag (or configure a network security config) — the API has no TLS by
> design at this stage.

## Run

1. On the laptop: `paios serve` (binds 127.0.0.1 by default — start it
   with a LAN-reachable host via `python -m paios.api --host 0.0.0.0`
   to accept the phone).
2. On the phone: install/run the app, open **Settings**, set the
   Backend URL, e.g. `http://192.168.1.15:8765`.

## Test

```
flutter test                                  # all suites
flutter test --update-goldens test/golden_test.dart   # seed golden baselines once
```
