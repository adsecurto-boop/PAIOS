// Settings.copyWith preserves unrelated fields (M25) — so saving the
// server URL never wipes the relay config or the pairing token.
import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/settings_service.dart';

void main() {
  Settings base() => Settings(
        baseUrl: 'http://192.168.1.5:8765',
        deviceToken: 'tok',
        deviceName: 'Phone',
        relayUrl: 'https://relay.example.com',
        account: 'me',
      );

  test('changing the URL preserves relay and pairing', () {
    final updated = base().copyWith(baseUrl: 'http://10.0.0.2:8765');
    expect(updated.baseUrl, 'http://10.0.0.2:8765');
    expect(updated.relayUrl, 'https://relay.example.com');
    expect(updated.account, 'me');
    expect(updated.deviceToken, 'tok');
  });

  test('saving relay preserves the pairing token', () {
    final updated = base().copyWith(relayUrl: 'https://new.example.com');
    expect(updated.relayUrl, 'https://new.example.com');
    expect(updated.deviceToken, 'tok');
  });

  test('clearToken forgets the pairing but keeps everything else', () {
    final updated = base().copyWith(clearToken: true, deviceName: '');
    expect(updated.deviceToken, isNull);
    expect(updated.relayUrl, 'https://relay.example.com');
    expect(updated.baseUrl, 'http://192.168.1.5:8765');
  });

  test('a plain copyWith never accidentally unpairs', () {
    expect(base().copyWith(refreshSeconds: 30).deviceToken, 'tok');
  });
}
