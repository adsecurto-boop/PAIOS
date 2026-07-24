// Dark-first Material 3 theme. Static colors, no animations beyond
// Material defaults - the desktop dashboard's restraint, on a phone.
import 'package:flutter/material.dart';

const Color _seed = Color(0xFF4C9BE8); // the desktop accent

/// Named ...Data so it never reads as the boolean preference of the same
/// name that AppState publishes.
ThemeData darkThemeData() => ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: _seed,
        brightness: Brightness.dark,
        surface: const Color(0xFF14161A),
      ),
      scaffoldBackgroundColor: const Color(0xFF14161A),
      // Card styling stays at Material 3 defaults: the CardTheme /
      // CardThemeData signature changed across recent Flutter versions,
      // and version-portability beats a border.
    );

ThemeData lightTheme() => ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(seedColor: _seed),
    );
