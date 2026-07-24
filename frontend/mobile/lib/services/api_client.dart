// The REST client: the phone's only doorway into PAIOS.
//
// One method per endpoint; every user action calls exactly one method
// and every method issues exactly one request. Failures become:
//  - ApiUnreachableException  (no route to the laptop; go offline)
//  - ApiTimeoutException      (a SUBTYPE of the above: the laptop
//    accepted the connection but did not answer in time - a different
//    fact, and the one an AI round trip produces)
//  - ApiResponseException     (the API answered with an error payload)
//
// Deadlines are per call, not per client. Polling wants a short one so a
// hung desktop cannot freeze the phone; an assistant question runs
// through a local language model and legitimately takes a minute. One
// number cannot serve both, and using the poll deadline for the
// assistant is why a working desktop reported "Server unreachable".
import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiUnreachableException implements Exception {
  final String detail;
  ApiUnreachableException(this.detail);
  @override
  String toString() => 'Server unreachable: $detail';
}

/// The server was reached but stayed silent past the deadline. Callers
/// that can wait (the assistant) tell the user to wait; the poll loop
/// still treats it as an outage, which is right for a poll.
class ApiTimeoutException extends ApiUnreachableException {
  final Duration waited;
  ApiTimeoutException(this.waited)
      : super('no answer within ${waited.inSeconds}s');
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
  /// Poll/action deadline: the desktop is a LAN hop away.
  static const Duration defaultTimeout = Duration(seconds: 5);

  /// Deadline for calls the desktop answers by asking a language model.
  /// It matches the backend's own completion ceiling, so the phone never
  /// gives up on a request the desktop is still working on.
  static const Duration aiTimeout = Duration(seconds: 300);

  final String baseUrl;
  final Duration timeout;
  final http.Client _http;

  /// M21: the bearer token minted by device pairing. When present it is
  /// sent as `Authorization: Bearer <token>` on `/mobile` calls only;
  /// every legacy endpoint stays exactly as it was (additive contract).
  String? authToken;

  ApiClient(String url,
      {this.timeout = defaultTimeout, http.Client? client, this.authToken})
      : baseUrl = normalizeUrl(url),
        _http = client ?? http.Client();

  /// The one place a typed address becomes a usable base URL: trims,
  /// drops a trailing '/', and supplies http:// when the scheme is
  /// missing. Public because the connection probe MUST normalize the
  /// same way this client does - probing the raw text reported a
  /// perfectly reachable desktop as unreachable.
  static String normalizeUrl(String url) {
    var text = url.trim();
    while (text.endsWith('/')) {
      text = text.substring(0, text.length - 1);
    }
    if (!text.startsWith('http://') && !text.startsWith('https://')) {
      text = 'http://$text';
    }
    return text;
  }

  void close() => _http.close();

  /// Test seam: issue one request with an explicit deadline. Production
  /// code calls the typed methods; this only exists so a test can drive
  /// the AI path with a short deadline instead of the real five minutes.
  @visibleForTesting
  Future<dynamic> requestForTest(String method, String path,
          [Map<String, dynamic>? body, Duration? deadline]) =>
      _request(method, path, body, deadline);

  void _log(String message) {
    if (kReleaseMode) return;
    developer.log(message, name: 'paios.api');
  }

  Future<dynamic> _request(String method, String path,
      [Map<String, dynamic>? body, Duration? deadline]) async {
    final wait = deadline ?? timeout;
    final uri = Uri.parse('$baseUrl$path');
    final headers = <String, String>{
      'Content-Type': 'application/json; charset=utf-8',
      if (authToken != null && path.startsWith('/mobile'))
        'Authorization': 'Bearer $authToken',
    };
    final started = DateTime.now();
    _log('-> $method $uri '
        'auth=${headers.containsKey('Authorization')} '
        'timeout=${wait.inSeconds}s body=${body == null ? '{}' : jsonEncode(body)}');
    http.Response response;
    try {
      switch (method) {
        case 'GET':
          response = await _http.get(uri, headers: headers).timeout(wait);
        case 'PUT':
          response = await _http
              .put(uri, headers: headers, body: jsonEncode(body ?? {}))
              .timeout(wait);
        case 'DELETE':
          response = await _http
              .delete(uri, headers: headers, body: jsonEncode(body ?? {}))
              .timeout(wait);
        default:
          response = await _http
              .post(uri, headers: headers, body: jsonEncode(body ?? {}))
              .timeout(wait);
      }
    } on TimeoutException {
      _log('<- $method $uri TIMEOUT after ${wait.inSeconds}s');
      throw ApiTimeoutException(wait);
    } on SocketException catch (error) {
      _log('<- $method $uri SOCKET ${error.message}');
      throw ApiUnreachableException(error.message);
    } on http.ClientException catch (error) {
      _log('<- $method $uri CLIENT ${error.message}');
      throw ApiUnreachableException(error.message);
    }
    final elapsed = DateTime.now().difference(started).inMilliseconds;
    _log('<- $method $uri ${response.statusCode} in ${elapsed}ms '
        '(${response.bodyBytes.length} bytes)');
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
      final failure = ApiResponseException(
        response.statusCode,
        error?['type'] as String? ?? 'HttpError',
        error?['message'] as String? ?? 'HTTP ${response.statusCode}',
      );
      _log('<- $method $uri ERROR ${failure.errorType}: ${failure.message}');
      throw failure;
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

  // --- M20: event creation and editing ------------------------------------

  /// Builds the shared create/edit body: only fields the caller set are
  /// sent, so the API's defaults stay in charge.
  static Map<String, dynamic> _eventBody({
    required String title,
    String? mode,
    String? suggestedTime,
    double? priority,
    String? expectedOutcome,
    Map<String, dynamic>? metadata,
  }) =>
      {
        'title': title,
        if (mode != null) 'mode': mode,
        if (suggestedTime != null) 'suggested_time': suggestedTime,
        if (priority != null) 'priority': priority,
        if (expectedOutcome != null) 'expected_outcome': expectedOutcome,
        if (metadata != null && metadata.isNotEmpty) 'metadata': metadata,
      };

  Future<Map<String, dynamic>> createEvent({
    required String title,
    String? mode,
    String? suggestedTime,
    double? priority,
    String? expectedOutcome,
    Map<String, dynamic>? metadata,
  }) async =>
      await _request(
          'POST',
          '/events',
          _eventBody(
              title: title,
              mode: mode,
              suggestedTime: suggestedTime,
              priority: priority,
              expectedOutcome: expectedOutcome,
              metadata: metadata)) as Map<String, dynamic>;

  Future<Map<String, dynamic>> editEvent(
    String id, {
    required String title,
    String? mode,
    String? suggestedTime,
    double? priority,
    String? expectedOutcome,
    Map<String, dynamic>? metadata,
  }) async =>
      await _request(
          'PUT',
          '/events/$id',
          _eventBody(
              title: title,
              mode: mode,
              suggestedTime: suggestedTime,
              priority: priority,
              expectedOutcome: expectedOutcome,
              metadata: metadata)) as Map<String, dynamic>;

  Future<Map<String, dynamic>> duplicateEvent(String id,
          {String? suggestedTime}) async =>
      await _request(
          'POST',
          '/events/$id/duplicate',
          suggestedTime == null
              ? {}
              : {'suggested_time': suggestedTime}) as Map<String, dynamic>;

  Future<Map<String, dynamic>> getEventMetadata(String id) async =>
      await _request('GET', '/events/$id/metadata') as Map<String, dynamic>;

  Future<Map<String, dynamic>> setEventMetadata(
          String id, Map<String, dynamic> fields) async =>
      await _request('PUT', '/events/$id/metadata', fields)
          as Map<String, dynamic>;

  // --- M20: goals and projects (used by the planning Apply step) ----------

  Future<Map<String, dynamic>> createGoal(
          {required String name, String? description}) async =>
      await _request('POST', '/goals', {
        'name': name,
        if (description != null) 'description': description,
      }) as Map<String, dynamic>;

  Future<Map<String, dynamic>> createProject(
          {required String name, String? description}) async =>
      await _request('POST', '/projects', {
        'name': name,
        if (description != null) 'description': description,
      }) as Map<String, dynamic>;

  // --- M20: plan -----------------------------------------------------------

  Future<Map<String, dynamic>> getPlan() async =>
      await _request('GET', '/plan') as Map<String, dynamic>;

  // --- M20: inbox ----------------------------------------------------------

  Future<List<Map<String, dynamic>>> getInbox() => _list('/inbox', 'items');

  Future<Map<String, dynamic>> addInbox(String text) async =>
      await _request('POST', '/inbox', {'text': text}) as Map<String, dynamic>;

  Future<Map<String, dynamic>> convertInbox(
    String id, {
    required String to,
    String? title,
    String? suggestedTime,
  }) async =>
      await _request('POST', '/inbox/$id/convert', {
        'to': to,
        if (title != null) 'title': title,
        if (suggestedTime != null) 'suggested_time': suggestedTime,
      }) as Map<String, dynamic>;

  Future<void> archiveInbox(String id) =>
      _request('POST', '/inbox/$id/archive');

  Future<void> deleteInbox(String id) => _request('DELETE', '/inbox/$id');

  // --- M20: templates -------------------------------------------------------

  Future<List<Map<String, dynamic>>> getTemplates() =>
      _list('/templates', 'templates');

  Future<Map<String, dynamic>> instantiateTemplate(String id,
          {String? suggestedTime}) async =>
      await _request(
          'POST',
          '/templates/$id/instantiate',
          suggestedTime == null
              ? {}
              : {'suggested_time': suggestedTime}) as Map<String, dynamic>;

  // --- M20: assistant -------------------------------------------------------

  Future<Map<String, dynamic>> assistantStatus() async =>
      await _request('GET', '/assistant/status') as Map<String, dynamic>;

  Future<Map<String, dynamic>> assistantPlan(String text) async =>
      await _request('POST', '/assistant/plan', {'text': text})
          as Map<String, dynamic>;

  Future<Map<String, dynamic>> assistantExplainDay() async =>
      await _request('POST', '/assistant/explain-day', {})
          as Map<String, dynamic>;

  // --- M21: mobile companion (paired-device namespace) ---------------------
  //
  // Every endpoint below lives under /mobile. Pairing and token
  // validation are open; everything else requires the bearer token
  // ([authToken]) and answers 401 when it is missing or revoked.

  /// Exchanges the 6-digit desktop code for a device token. The token
  /// is shown exactly once - the caller must store it (Settings).
  Future<Map<String, dynamic>> pairDevice(
          String code, String deviceName) async =>
      await _request('POST', '/mobile/pair',
          {'code': code, 'device_name': deviceName}) as Map<String, dynamic>;

  /// Checks a stored token (app start / Settings "Test connection").
  Future<Map<String, dynamic>> validateToken(String token) async =>
      await _request('POST', '/mobile/auth', {'token': token})
          as Map<String, dynamic>;

  Future<Map<String, dynamic>> mobileTimeline() async =>
      await _request('GET', '/mobile/timeline') as Map<String, dynamic>;

  Future<Map<String, dynamic>> mobileTasks() async =>
      await _request('GET', '/mobile/tasks') as Map<String, dynamic>;

  Future<Map<String, dynamic>> createMobileTask(
          {required String title, double? priority}) async =>
      await _request('POST', '/mobile/tasks', {
        'title': title,
        if (priority != null) 'priority': priority,
      }) as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> mobileLogs({String? day}) =>
      _list(day == null ? '/mobile/logs' : '/mobile/logs/$day', 'entries');

  /// Idempotent by [clientId]: resubmitting the same client_id returns
  /// the original record - the offline-queue contract.
  Future<Map<String, dynamic>> createMobileLog({
    required String kind,
    required String text,
    String? at,
    String? clientId,
  }) async =>
      await _request('POST', '/mobile/logs', {
        'kind': kind,
        'text': text,
        if (at != null) 'at': at,
        if (clientId != null) 'client_id': clientId,
      }) as Map<String, dynamic>;

  Future<Map<String, dynamic>> mobileStudy() async =>
      await _request('GET', '/mobile/study') as Map<String, dynamic>;

  /// One question, one answer. source=="heuristic" means the desktop
  /// has no AI provider - still an answer, never an error.
  ///
  /// The desktop answers this by running a language model, so it gets
  /// the AI deadline, not the poll deadline. The phone still talks only
  /// to the desktop: the model lives there and is never contacted from
  /// here.
  Future<Map<String, dynamic>> assistantQuery(String text) async =>
      await _request('POST', '/mobile/assistant/query', {'text': text},
          aiTimeout) as Map<String, dynamic>;
}
