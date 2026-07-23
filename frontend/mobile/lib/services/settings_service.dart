// Preferences: server URL, refresh interval, theme. One of the three
// permitted local stores (no domain state).
import 'package:shared_preferences/shared_preferences.dart';

class Settings {
  static const defaultBaseUrl = 'http://192.168.1.15:8765';
  static const defaultRefreshSeconds = 10;

  String baseUrl;
  int refreshSeconds;
  bool darkTheme;

  /// M21: the bearer token from device pairing (null = not paired).
  /// The desktop shows it exactly once, so this copy is the only one.
  String? deviceToken;
  String deviceName;

  /// M25 (remote access): the relay endpoint + account the phone falls
  /// back to when it is not on the desktop's Wi-Fi. Empty = LAN only.
  String relayUrl;
  String account;

  Settings({
    this.baseUrl = defaultBaseUrl,
    this.refreshSeconds = defaultRefreshSeconds,
    this.darkTheme = true,
    this.deviceToken,
    this.deviceName = '',
    this.relayUrl = '',
    this.account = 'default',
  });

  /// A copy with selected fields changed. ``clearToken: true`` forgets
  /// the pairing (deviceToken is otherwise preserved, so a plain
  /// copyWith never accidentally unpairs the device).
  Settings copyWith({
    String? baseUrl,
    int? refreshSeconds,
    bool? darkTheme,
    String? deviceToken,
    String? deviceName,
    String? relayUrl,
    String? account,
    bool clearToken = false,
  }) =>
      Settings(
        baseUrl: baseUrl ?? this.baseUrl,
        refreshSeconds: refreshSeconds ?? this.refreshSeconds,
        darkTheme: darkTheme ?? this.darkTheme,
        deviceToken: clearToken ? null : (deviceToken ?? this.deviceToken),
        deviceName: deviceName ?? this.deviceName,
        relayUrl: relayUrl ?? this.relayUrl,
        account: account ?? this.account,
      );
}

class SettingsService {
  static const _keyBaseUrl = 'base_url';
  static const _keyRefresh = 'refresh_seconds';
  static const _keyDark = 'dark_theme';
  static const _keyDeviceToken = 'device_token';
  static const _keyDeviceName = 'device_name';
  static const _keyRelayUrl = 'relay_url';
  static const _keyAccount = 'relay_account';
  static const keyDashboardCache = 'dashboard_cache';
  static const keyNotifications = 'notification_history';
  static const keyEventsCache = 'events_cache';
  static const keyPlanCache = 'plan_cache';
  static const keyInboxCache = 'inbox_cache';
  static const keyJournalCache = 'journal_cache';
  static const keyStudyCache = 'study_cache';
  static const keyOfflineQueue = 'offline_log_queue';

  final SharedPreferences _prefs;

  SettingsService(this._prefs);

  static Future<SettingsService> load() async =>
      SettingsService(await SharedPreferences.getInstance());

  Settings read() => Settings(
        baseUrl: _prefs.getString(_keyBaseUrl) ?? Settings.defaultBaseUrl,
        refreshSeconds:
            _prefs.getInt(_keyRefresh) ?? Settings.defaultRefreshSeconds,
        darkTheme: _prefs.getBool(_keyDark) ?? true,
        deviceToken: _prefs.getString(_keyDeviceToken),
        deviceName: _prefs.getString(_keyDeviceName) ?? '',
        relayUrl: _prefs.getString(_keyRelayUrl) ?? '',
        account: _prefs.getString(_keyAccount) ?? 'default',
      );

  Future<void> write(Settings settings) async {
    await _prefs.setString(_keyBaseUrl, settings.baseUrl);
    await _prefs.setInt(_keyRefresh, settings.refreshSeconds);
    await _prefs.setBool(_keyDark, settings.darkTheme);
    final token = settings.deviceToken;
    if (token == null) {
      await _prefs.remove(_keyDeviceToken); // "Forget pairing"
    } else {
      await _prefs.setString(_keyDeviceToken, token);
    }
    await _prefs.setString(_keyDeviceName, settings.deviceName);
    await _prefs.setString(_keyRelayUrl, settings.relayUrl);
    await _prefs.setString(_keyAccount, settings.account);
  }

  String? readString(String key) => _prefs.getString(key);

  Future<void> writeString(String key, String value) =>
      _prefs.setString(key, value);
}
