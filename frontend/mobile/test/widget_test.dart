// Widget tests: the shell over mocked REST - dashboard cards, drawer
// navigation, actions, offline banner, settings.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:paios_mobile/main.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fixtures.dart';

class RequestLog {
  final List<String> requests = [];
  final List<String> bodies = []; // POST/PUT payloads, in request order
}

ApiClient Function(String) mockFactory(RequestLog log,
    {bool offline = false, List<Map<String, dynamic>>? events}) {
  // Stateful inbox: archive/delete mutate it, exactly like the real
  // backend — a dismissed row must not resurrect unchanged on refresh.
  final inbox =
      (inboxJson()['items'] as List).cast<Map<String, dynamic>>().toList();
  return (url) => ApiClient(url,
      client: MockClient((request) async {
        if (offline) throw http.ClientException('connection refused');
        log.requests.add('${request.method} ${request.url.path}');
        if (request.method == 'POST' || request.method == 'PUT') {
          log.bodies.add(request.body);
        }
        final path = request.url.path;
        final archiveMatch =
            RegExp(r'^/inbox/([^/]+)/archive$').firstMatch(path);
        if (archiveMatch != null && request.method == 'POST') {
          for (final item in inbox) {
            if (item['id'] == archiveMatch.group(1)) {
              item['status'] = 'archived';
            }
          }
          return http.Response(jsonEncode({'result': 'ok'}), 200);
        }
        final deleteMatch = RegExp(r'^/inbox/([^/]+)$').firstMatch(path);
        if (deleteMatch != null && request.method == 'DELETE') {
          inbox.removeWhere((item) => item['id'] == deleteMatch.group(1));
          return http.Response(jsonEncode({'result': 'deleted'}), 200);
        }
        if (path == '/dashboard') {
          return http.Response(jsonEncode(dashboardJson()), 200);
        }
        if (path == '/resources') {
          return http.Response(
              jsonEncode({'resources': resourcesJson()}), 200);
        }
        if (path == '/events' && request.method == 'GET') {
          return http.Response(
              jsonEncode({'events': events ?? eventsJson()}), 200);
        }
        if (path == '/recommendations') {
          return http.Response(
              jsonEncode({
                'recommendations':
                    dashboardJson()['recommendations'] as List
              }),
              200);
        }
        // --- M20 routes -----------------------------------------------------
        if (path == '/plan') {
          return http.Response(jsonEncode(planJson()), 200);
        }
        if (path == '/inbox' && request.method == 'GET') {
          return http.Response(jsonEncode({'items': inbox}), 200);
        }
        if (path == '/templates') {
          return http.Response(jsonEncode(templatesJson()), 200);
        }
        if (path == '/assistant/status') {
          return http.Response(jsonEncode(assistantStatusJson()), 200);
        }
        if (path == '/assistant/plan') {
          return http.Response(jsonEncode(assistantPlanJson()), 200);
        }
        if (path == '/assistant/explain-day') {
          return http.Response(jsonEncode(assistantExplainJson()), 200);
        }
        if (path == '/events/e1/metadata' && request.method == 'GET') {
          return http.Response(jsonEncode(eventMetadataJson()), 200);
        }
        if (path == '/events' && request.method == 'POST') {
          return http.Response(jsonEncode(createEventResponseJson()), 201);
        }
        if (request.method == 'POST' ||
            request.method == 'PUT' ||
            request.method == 'DELETE') {
          return http.Response(jsonEncode({'result': 'ok'}), 200);
        }
        return http.Response(
            jsonEncode({
              'error': {'type': 'ApiError', 'message': 'unknown'}
            }),
            404);
      }));
}

Future<AppState> makeState(RequestLog log, {bool offline = false}) async {
  SharedPreferences.setMockInitialValues({});
  final store = SettingsService(await SharedPreferences.getInstance());
  return AppState(store,
      clientFactory: mockFactory(log, offline: offline));
}

/// Opens the drawer and taps [title], scrolling the drawer list first —
/// the M21 destinations made it taller than a phone-sized viewport.
Future<void> openScreen(WidgetTester tester, String title) async {
  await tester.tap(find.byTooltip('Open navigation menu'));
  await tester.pumpAndSettle();
  final drawer = find.byType(Drawer);
  // The drawer ListView builds lazily: off-screen entries have no
  // element yet, so the finder must stay unevaluated (no .last) until
  // dragUntilVisible has scrolled them into existence.
  final entry = find.descendant(
      of: drawer, matching: find.textContaining(title));
  await tester.dragUntilVisible(
    entry,
    find.descendant(of: drawer, matching: find.byType(ListView)).first,
    const Offset(0, -80),
  );
  await tester.pumpAndSettle();
  await tester.tap(entry.last);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('dashboard shows every mission card', (tester) async {
    // A tall surface so the lazy ListView mounts every card at once.
    tester.view.physicalSize = const Size(800, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final state = await makeState(RequestLog());
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    // M20: Planning is the initial screen; hop to Dashboard first
    // (wide surface, so the NavigationRail label is tappable directly).
    await tester.tap(find.text('Dashboard'));
    await tester.pumpAndSettle();

    for (final title in [
      'TIME', 'STATUS', 'CURRENT EVENT', 'CURRENT CONTEXT', 'GOALS',
      'PROJECTS', 'RECOMMENDATIONS', 'HEALTH', 'RESOURCES', 'LEARNING',
      'RECENT REFLECTION', 'NOTIFICATIONS',
    ]) {
      expect(find.text(title), findsOneWidget,
          reason: 'missing dashboard card: $title');
    }
    expect(find.text('Idle — no running event.'), findsOneWidget);
    expect(find.textContaining('Learn Sanskrit'), findsWidgets);
    state.dispose();
  });

  testWidgets('drawer navigates to every screen', (tester) async {
    final state = await makeState(RequestLog());
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    for (final title in [
      'Timeline', 'Quick Capture', 'Recommendations', 'Events', 'Goals',
      'Projects', 'Contexts', 'Resources', 'Reflections',
      'Daily Journal', 'Study', 'AI Assistant', 'Settings',
    ]) {
      await openScreen(tester, title);
      expect(find.widgetWithText(AppBar, title), findsOneWidget,
          reason: 'did not land on $title');
    }
    state.dispose();
  });

  testWidgets('events screen action calls exactly one endpoint',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Events').last);
    await tester.pumpAndSettle();
    expect(find.text('Deep work'), findsOneWidget);

    log.requests.clear();
    await tester.tap(find.byType(PopupMenuButton<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Archive'));
    await tester.pumpAndSettle();

    expect(log.requests.where((r) => r.startsWith('POST')).toList(),
        ['POST /events/e1/archive']);
    state.dispose();
  });

  testWidgets('recommendation accept calls the accept endpoint',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Recommendations').last);
    await tester.pumpAndSettle();

    log.requests.clear();
    await tester.tap(find.text('Accept'));
    await tester.pumpAndSettle();
    expect(log.requests.where((r) => r.startsWith('POST')).toList(),
        ['POST /recommendations/r1/accept']);
    state.dispose();
  });

  testWidgets('offline shows the banner and never crashes', (tester) async {
    final state = await makeState(RequestLog(), offline: true);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    expect(find.textContaining('OFFLINE'), findsOneWidget);
    expect(tester.takeException(), isNull);
    state.dispose();
  });

  testWidgets('notifications screen marks read and clears', (tester) async {
    final state = await makeState(RequestLog());
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();
    // The connect notice is unread.
    expect(state.center.unreadCount, greaterThan(0));

    await openScreen(tester, 'Notifications');

    await tester.tap(find.text('Mark all read'));
    await tester.pumpAndSettle();
    expect(state.center.unreadCount, 0);

    await tester.tap(find.text('Clear'));
    await tester.pumpAndSettle();
    expect(find.text('No notifications.'), findsOneWidget);
    state.dispose();
  });

  testWidgets('settings edits the server URL', (tester) async {
    final state = await makeState(RequestLog());
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await openScreen(tester, 'Settings');

    await tester.enterText(
        find.byType(TextField).first, 'http://10.0.0.7:8765');
    await tester.tap(find.text('Save server'));
    await tester.pumpAndSettle();

    expect(state.settings.baseUrl, 'http://10.0.0.7:8765');
    expect(state.client.baseUrl, 'http://10.0.0.7:8765');
    state.dispose();
  });
}
