// Parsing the desktop's pairing payload (M25).
import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/pairing_payload.dart';

void main() {
  test('parses a full paios://pair payload', () {
    final payload = PairingPayload.parse(
        'paios://pair?lan=http://192.168.1.5:8765&relay=https://relay.example.com&account=me');
    expect(payload.lanUrl, 'http://192.168.1.5:8765');
    expect(payload.relayUrl, 'https://relay.example.com');
    expect(payload.account, 'me');
    expect(payload.hasLan, isTrue);
    expect(payload.hasRelay, isTrue);
    expect(payload.isUsable, isTrue);
  });

  test('parses a LAN-only payload with default account', () {
    final payload =
        PairingPayload.parse('paios://pair?lan=http://192.168.1.5:8765');
    expect(payload.lanUrl, 'http://192.168.1.5:8765');
    expect(payload.hasRelay, isFalse);
    expect(payload.account, 'default');
  });

  test('accepts a plain URL', () {
    final payload = PairingPayload.parse('http://192.168.1.5:8765');
    expect(payload.lanUrl, 'http://192.168.1.5:8765');
    expect(payload.isUsable, isTrue);
  });

  test('accepts a bare host:port a user typed', () {
    final payload = PairingPayload.parse('192.168.1.5:8765');
    expect(payload.lanUrl, 'http://192.168.1.5:8765');
  });

  test('unrecognised text yields an unusable payload', () {
    final payload = PairingPayload.parse('hello there');
    expect(payload.isUsable, isFalse);
  });
}
