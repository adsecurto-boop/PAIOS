// LAN -> Relay -> Offline auto-selection (M25), against in-process mock
// servers so the whole decision runs with no real network.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/connection_manager.dart';

class MockLan {
  late HttpServer server;
  String get url => 'http://127.0.0.1:${server.port}';
  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      final r = request.response;
      r.statusCode = 200;
      r.headers.contentType = ContentType.json;
      r.write(jsonEncode({'operational': true}));
      await r.close();
    });
  }

  Future<void> stop() => server.close(force: true);
}

class MockRelay {
  late HttpServer server;
  String get url => 'http://127.0.0.1:${server.port}';
  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      final r = request.response;
      r.statusCode = 200;
      r.headers.contentType = ContentType.json;
      if (request.uri.path == '/phone/token') {
        r.write(jsonEncode({
          'access_token': 'a',
          'refresh_token': 'r',
        }));
      } else {
        r.write(jsonEncode({'status': 200, 'body': {}}));
      }
      await r.close();
    });
  }

  Future<void> stop() => server.close(force: true);
}

void main() {
  test('LAN is chosen first when the desktop is on this Wi-Fi', () async {
    final lan = MockLan();
    await lan.start();
    final manager = ConnectionManager(
      lanUrl: lan.url,
      relayUrl: 'https://relay.example.com',
      account: 'me',
      deviceToken: 'tok',
      lanProbeTimeout: const Duration(seconds: 1),
    );
    final connection = await manager.resolve();
    expect(connection.mode, ConnectionMode.lan);
    expect(connection.mode.label, 'On your Wi-Fi');
    connection.client.close();
    await lan.stop();
  });

  test('falls back to the relay when LAN is unreachable', () async {
    final relay = MockRelay();
    await relay.start();
    final manager = ConnectionManager(
      lanUrl: 'http://127.0.0.1:9', // nothing listening
      relayUrl: relay.url,
      account: 'me',
      deviceToken: 'tok',
      lanProbeTimeout: const Duration(milliseconds: 300),
    );
    final connection = await manager.resolve();
    expect(connection.mode, ConnectionMode.remote);
    expect(connection.mode.label, 'Connected from anywhere');
    connection.client.close();
    await relay.stop();
  });

  test('goes offline when neither LAN nor relay is available', () async {
    final manager = ConnectionManager(
      lanUrl: 'http://127.0.0.1:9',
      lanProbeTimeout: const Duration(milliseconds: 300),
    );
    final connection = await manager.resolve();
    expect(connection.mode, ConnectionMode.offline);
    expect(connection.mode.label, 'Offline');
    connection.client.close();
  });

  test('offline when relay is set but the device is not paired', () async {
    final manager = ConnectionManager(
      lanUrl: 'http://127.0.0.1:9',
      relayUrl: 'https://relay.example.com',
      account: 'me',
      deviceToken: null, // not paired
      lanProbeTimeout: const Duration(milliseconds: 300),
    );
    final connection = await manager.resolve();
    expect(connection.mode, ConnectionMode.offline);
    connection.client.close();
  });
}
