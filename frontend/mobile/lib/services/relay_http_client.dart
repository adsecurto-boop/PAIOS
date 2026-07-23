// Remote-access transport (M25): make the ordinary ApiClient work
// through the PAIOS relay without changing a single one of its methods.
//
// This is an http.Client that intercepts every outgoing request and
// re-wraps it in the relay's envelope:
//   POST <relay>/phone/request
//   Authorization: Bearer <jwt>
//   { method, path, body, headers:{Authorization: Bearer <device_token>},
//     nonce, ts }
// The desktop executes it against its local API and the relay returns
// { status, body }, which we hand back as a normal HTTP response. So the
// whole app is oblivious to whether it is on Wi-Fi or on mobile data.
import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;

class RelayAuthException implements Exception {
  final String detail;
  RelayAuthException(this.detail);
  @override
  String toString() => detail;
}

class RelayHttpClient extends http.BaseClient {
  final String relayUrl;
  final String account;
  final String deviceToken;
  final http.Client _inner;
  final Random _random = Random.secure();

  String? _accessToken;
  String? _refreshToken;

  RelayHttpClient({
    required String relayUrl,
    required this.account,
    required this.deviceToken,
    http.Client? inner,
  })  : relayUrl = _normalize(relayUrl),
        _inner = inner ?? http.Client();

  static String _normalize(String url) {
    var text = url.trim();
    if (text.endsWith('/')) text = text.substring(0, text.length - 1);
    if (!text.startsWith('http://') && !text.startsWith('https://')) {
      text = 'https://$text';
    }
    return text;
  }

  @override
  void close() => _inner.close();

  /// Obtain the first access/refresh pair (called once, before use).
  Future<void> authenticate() async {
    final response = await _inner.post(
      Uri.parse('$relayUrl/phone/token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'account': account, 'device_token': deviceToken}),
    );
    if (response.statusCode != 200) {
      throw RelayAuthException(
          'the relay refused this device (${response.statusCode})');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    _accessToken = data['access_token'] as String?;
    _refreshToken = data['refresh_token'] as String?;
    if (_accessToken == null) {
      throw RelayAuthException('the relay did not return a token');
    }
  }

  String _nonce() =>
      '${DateTime.now().microsecondsSinceEpoch}-${_random.nextInt(1 << 32)}';

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (_accessToken == null) {
      await authenticate();
    }
    final bodyText = request is http.Request ? request.body : '';
    dynamic body;
    if (bodyText.isNotEmpty) {
      try {
        body = jsonDecode(bodyText);
      } catch (_) {
        body = bodyText;
      }
    }
    final path = request.url.path +
        (request.url.hasQuery ? '?${request.url.query}' : '');
    final envelope = {
      'method': request.method,
      'path': path,
      if (body != null) 'body': body,
      'headers': {
        if (request.headers['Authorization'] != null)
          'Authorization': request.headers['Authorization'],
      },
      'nonce': _nonce(),
      'ts': DateTime.now().millisecondsSinceEpoch ~/ 1000,
    };

    var relayResponse = await _postEnvelope(envelope);
    if (relayResponse.statusCode == 401 && await _tryRefresh()) {
      relayResponse = await _postEnvelope({...envelope, 'nonce': _nonce()});
    }
    return _unwrap(relayResponse);
  }

  Future<http.Response> _postEnvelope(Map<String, dynamic> envelope) {
    return _inner.post(
      Uri.parse('$relayUrl/phone/request'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $_accessToken',
      },
      body: jsonEncode(envelope),
    );
  }

  Future<bool> _tryRefresh() async {
    if (_refreshToken == null) return false;
    final response = await _inner.post(
      Uri.parse('$relayUrl/phone/refresh'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': _refreshToken}),
    );
    if (response.statusCode != 200) return false;
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    _accessToken = data['access_token'] as String?;
    _refreshToken = data['refresh_token'] as String? ?? _refreshToken;
    return _accessToken != null;
  }

  http.StreamedResponse _unwrap(http.Response relayResponse) {
    // The relay's own transport errors (auth, offline desktop) surface as
    // that status with the relay's JSON message; a delivered request
    // returns 200 wrapping the desktop's real {status, body}.
    if (relayResponse.statusCode != 200) {
      return _synth(relayResponse.statusCode, relayResponse.body);
    }
    final data = jsonDecode(relayResponse.body) as Map<String, dynamic>;
    final status = (data['status'] as num?)?.toInt() ?? 502;
    final innerBody = data['body'];
    final text = innerBody is String ? innerBody : jsonEncode(innerBody);
    return _synth(status, text);
  }

  http.StreamedResponse _synth(int status, String body) {
    final bytes = utf8.encode(body);
    return http.StreamedResponse(
      Stream.value(bytes),
      status,
      contentLength: bytes.length,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );
  }
}
