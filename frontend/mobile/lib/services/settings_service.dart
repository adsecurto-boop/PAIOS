// Preferences: server URL, refresh interval, theme. One of the three
// permitted local stores (no domain state).
import 'package:shared_preferences/shared_preferences.dart';

class Settings {
  static const defaultBaseUrl = 'http://192.168.1.15:8765';
  static const defaultRefreshSeconds = 10;

  String baseUrl;
  int refreshSeconds;
  bool darkTheme;

  Settings({
    this.baseUrl = defaultBaseUrl,
    this.refreshSeconds = defaultRefreshSeconds,
    this.darkTheme = true,
  });
}

class SettingsService {
  static const _keyBaseUrl = 'base_url';
  static const _keyRefresh = 'refresh_seconds';
  static const _keyDark = 'dark_theme';
  static const keyDashboardCache = 'dashboard_cache';
  static const keyNotifications = 'notification_history';
  static const keyEventsCache = 'events_cache';
  static const keyPlanCache = 'plan_cache';
  static const keyInboxCache = 'inbox_cache';

  final SharedPreferences _prefs;

  SettingsService(this._prefs);

  static Future<SettingsService> load() async =>
      SettingsService(await SharedPreferences.getInstance());

  Settings read() => Settings(
        baseUrl: _prefs.getString(_keyBaseUrl) ?? Settings.defaultBaseUrl,
        refreshSeconds:
            _prefs.getInt(_keyRefresh) ?? Settings.defaultRefreshSeconds,
        darkTheme: _prefs.getBool(_keyDark) ?? true,
      );

  Future<void> write(Settings settings) async {
    await _prefs.setString(_keyBaseUrl, settings.baseUrl);
    await _prefs.setInt(_keyRefresh, settings.refreshSeconds);
    await _prefs.setBool(_keyDark, settings.darkTheme);
  }

  String? readString(String key) => _prefs.getString(key);

  Future<void> writeString(String key, String value) =>
      _prefs.setString(key, value);
}
