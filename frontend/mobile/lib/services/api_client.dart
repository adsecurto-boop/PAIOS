// The REST client: the phone's only doorway into PAIOS.
//
// One method per endpoint; every user action calls exactly one method
// and every method issues exactly one request. Failures become:
//  - ApiUnreachableException  (no route to the laptop; go offline)
//  - ApiResponseException     (the API answered with an error payload)
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class ApiUnreachableException implements Exception {
  final String detail;
  ApiUnreachableException(this.detail);
  @override
  String toString() => 'Server unreachable: $detail';
}

class ApiResponseException implements Exception {
  final int status;
  final String errorType;
  final String message;
  ApiResponseException(this.status, this.errorType, this.message);
  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  final Duration timeout;
  final http.Client _http;

  ApiClient(String url,
      {this.timeout = const Duration(seconds: 5), http.Client? client})
      : baseUrl = _normalize(url),
        _http = client ?? http.Client();

  static String _normalize(String url) {
    var text = url.trim();
    if (text.endsWith('/')) text = text.substring(0, text.length - 1);
    if (!text.startsWith('http://') && !text.startsWith('https://')) {
      text = 'http://$text';
    }
    return text;
  }

  void close() => _http.close();

  Future<dynamic> _request(String method, String path,
      [Map<String, dynamic>? body]) async {
    final uri = Uri.parse('$baseUrl$path');
    http.Response response;
    try {
      if (method == 'GET') {
        response = await _http.get(uri).timeout(timeout);
      } else {
        response = await _http
            .post(uri,
                headers: {'Content-Type': 'application/json; charset=utf-8'},
                body: jsonEncode(body ?? {}))
            .timeout(timeout);
      }
    } on TimeoutException {
      throw ApiUnreachableException('timed out after ${timeout.inSeconds}s');
    } on SocketException catch (error) {
      throw ApiUnreachableException(error.message);
    } on http.ClientException catch (error) {
      throw ApiUnreachableException(error.message);
    }
    final dynamic decoded;
    try {
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiResponseException(
          response.statusCode, 'BadPayload', 'Response was not JSON');
    }
    if (response.statusCode >= 400) {
      final error = decoded is Map<String, dynamic>
          ? decoded['error'] as Map<String, dynamic>?
          : null;
      throw ApiResponseException(
        response.statusCode,
        error?['type'] as String? ?? 'HttpError',
        error?['message'] as String? ?? 'HTTP ${response.statusCode}',
      );
    }
    return decoded;
  }

  // --- reads (polling) ---------------------------------------------------

  Future<Map<String, dynamic>> getDashboard() async =>
      await _request('GET', '/dashboard') as Map<String, dynamic>;

  Future<Map<String, dynamic>> getStatus() async =>
      await _request('GET', '/status') as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> _list(String path, String key) async {
    final payload = await _request('GET', path) as Map<String, dynamic>;
    return (payload[key] as List? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();
  }

  Future<List<Map<String, dynamic>>> getRecommendations() =>
      _list('/recommendations', 'recommendations');
  Future<List<Map<String, dynamic>>> getEvents() => _list('/events', 'events');
  Future<List<Map<String, dynamic>>> getGoals() => _list('/goals', 'goals');
  Future<List<Map<String, dynamic>>> getProjects() =>
      _list('/projects', 'projects');
  Future<List<Map<String, dynamic>>> getContexts() =>
      _list('/contexts', 'contexts');
  Future<List<Map<String, dynamic>>> getResources() =>
      _list('/resources', 'resources');
  Future<List<Map<String, dynamic>>> getReflections() =>
      _list('/reflections', 'reflections');

  // --- actions (one endpoint each) ---------------------------------------

  Future<void> acceptRecommendation(String id) =>
      _request('POST', '/recommendations/$id/accept');

  Future<void> rejectRecommendation(String id, {String? reason}) => _request(
      'POST',
      '/recommendations/$id/reject',
      reason == null ? {} : {'reason': reason});

  Future<void> startEvent(String id) => _request('POST', '/events/$id/start');

  Future<void> pauseEvent(String id) => _request('POST', '/events/$id/pause');

  Future<void> resumeEvent(String id) => _request('POST', '/events/$id/resume');

  Future<void> completeEvent(String id, {String? actualOutcome}) => _request(
      'POST',
      '/events/$id/complete',
      actualOutcome == null ? {} : {'actual_outcome': actualOutcome});

  Future<void> archiveEvent(String id) =>
      _request('POST', '/events/$id/archive');
}
