// Milestone 20 widget tests: planning propose/approve, quick capture,
// inbox swipe actions, timeline buckets (fixed clock), the create-event
// form, and the offline cache.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:paios_mobile/main.dart';
import 'package:paios_mobile/screens/planning_screen.dart';
import 'package:paios_mobile/screens/timeline_screen.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fixtures.dart';
import 'widget_test.dart' show RequestLog, mockFactory, makeState;

Future<AppState> makeStateWithPrefs(
  RequestLog log, {
  bool offline = false,
  List<Map<String, dynamic>>? events,
  Map<String, Object> prefs = const {},
}) async {
  SharedPreferences.setMockInitialValues(prefs);
  final store = SettingsService(await SharedPreferences.getInstance());
  return AppState(store,
      clientFactory: mockFactory(log, offline: offline, events: events));
}

void main() {
  testWidgets('planning: propose then approve calls only checked items',
      (tester) async {
    tester.view.physicalSize = const Size(800, 2000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    // Planning is the initial screen: type a brain dump, plan it.
    await tester.enterText(
        find.byType(TextField).first, 'report today, piano someday');
    await tester.tap(find.text('Plan it'));
    await tester.pumpAndSettle();

    // Three proposals; the duplicate starts unchecked -> Approve (2).
    expect(find.text('Finish quarterly report'), findsOneWidget);
    expect(find.text('Learn piano'), findsOneWidget);
    expect(find.text('duplicate'), findsOneWidget);
    expect(find.text('Approve (2)'), findsOneWidget);
    // The ambiguity question renders inline under the report card.
    expect(find.text('When is the report due?'), findsOneWidget);

    // Uncheck the first (event) proposal: only the goal stays checked.
    await tester.tap(find.byType(Checkbox).first);
    await tester.pumpAndSettle();
    expect(find.text('Approve (1)'), findsOneWidget);

    log.requests.clear();
    await tester.tap(find.text('Approve (1)'));
    await tester.pumpAndSettle();

    final posts =
        log.requests.where((r) => r.startsWith('POST')).toList();
    expect(posts, ['POST /goals']);
    expect(log.bodies.last, contains('Learn piano'));
    state.dispose();
  });

  testWidgets('quick capture: Enter captures instantly', (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quick Capture').last);
    await tester.pumpAndSettle();
    expect(find.text('Brain dump — capture now, organize later'),
        findsOneWidget);

    log.requests.clear();
    await tester.enterText(find.byType(TextField).first, 'Call the bank');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(log.requests, contains('POST /inbox'));
    expect(log.bodies.any((body) => body.contains('Call the bank')), isTrue);
    // The field cleared for the next thought.
    expect(
        (tester.widget(find.byType(TextField).first) as TextField)
            .controller!
            .text,
        isEmpty);
    state.dispose();
  });

  testWidgets('inbox swipe right archives via archiveInbox',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quick Capture').last);
    await tester.pumpAndSettle();
    expect(find.text('Buy milk'), findsOneWidget);

    log.requests.clear();
    await tester.drag(
        find.widgetWithText(Dismissible, 'Buy milk'), const Offset(500, 0));
    await tester.pumpAndSettle();

    expect(log.requests, contains('POST /inbox/i1/archive'));
    expect(log.requests.where((r) => r.startsWith('DELETE')), isEmpty);
    state.dispose();
  });

  testWidgets('inbox swipe left deletes only after confirmation',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quick Capture').last);
    await tester.pumpAndSettle();

    log.requests.clear();
    await tester.drag(
        find.widgetWithText(Dismissible, 'Buy milk'), const Offset(-500, 0));
    await tester.pumpAndSettle();
    expect(find.text('Delete captured item?'), findsOneWidget);
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();

    expect(log.requests, contains('DELETE /inbox/i1'));
    state.dispose();
  });

  testWidgets('timeline renders buckets from a fixed clock',
      (tester) async {
    tester.view.physicalSize = const Size(800, 2200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final state =
        await makeStateWithPrefs(RequestLog(), events: timelineEventsJson());
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: TimelineScreen(
          state: state,
          now: () => DateTime(2026, 7, 21, 9, 0),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    // NOW: the running event with progress and remaining time.
    expect(find.text('NOW'), findsOneWidget);
    expect(find.text('Review PRs'), findsOneWidget);
    expect(find.textContaining('30 min left'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);

    // NEXT: countdown to the 10:00 entry.
    expect(find.textContaining('in 1h 0m'), findsOneWidget);

    // Today bucket: upcoming, overdue and completed sections.
    expect(find.text('UPCOMING'), findsOneWidget);
    expect(find.text('Deep work'), findsOneWidget);
    expect(find.text('OVERDUE'), findsOneWidget);
    expect(find.text('Morning run'), findsOneWidget);
    expect(find.text('COMPLETED TODAY'), findsOneWidget);
    expect(find.text('Journal'), findsOneWidget);
    // Tomorrow's entry is not in today's bucket.
    expect(find.text('Write report'), findsNothing);
    // No drag-drop: the scheduler owns the schedule.
    expect(find.text('Schedule is controlled by the PAIOS Scheduler'),
        findsOneWidget);

    // Tomorrow bucket.
    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    expect(find.text('Write report'), findsOneWidget);
    expect(find.text('Deep work'), findsNothing);
    state.dispose();
  });

  testWidgets('event form sends metadata only when fields are set',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Events').last);
    await tester.pumpAndSettle();

    // Bare minimum: title only -> body is exactly {"title": ...}.
    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'Ship it');
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();
    expect(log.requests, contains('POST /events'));
    expect(jsonDecode(log.bodies.last), {'title': 'Ship it'});

    // Let the success SnackBar expire — it overlaps the FAB.
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();

    // With duration and tags -> metadata carries only those fields.
    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'Ship it again');
    await tester.enterText(find.byType(TextField).at(2), '45');
    await tester.enterText(find.byType(TextField).at(3), 'work, focus');
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();
    final body = jsonDecode(log.bodies.last) as Map<String, dynamic>;
    expect(body['title'], 'Ship it again');
    expect(body.containsKey('suggested_time'), isFalse);
    expect(body.containsKey('priority'), isFalse);
    expect(body.containsKey('project_id'), isFalse);
    expect(body['metadata'], {
      'tags': ['work', 'focus'],
      'estimated_duration_minutes': 45,
    });
    state.dispose();
  });

  testWidgets('event form includes project selector',
      (tester) async {
    final log = RequestLog();
    final state = await makeState(log);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Events').last);
    await tester.pumpAndSettle();

    // Open event form
    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    
    // Wait for projects to be fetched (async call in showEventForm)
    await tester.pumpAndSettle();
    
    // Verify project dropdown exists and shows "No Project" by default
    expect(find.text('Project'), findsOneWidget);
    expect(find.text('— No Project —'), findsOneWidget);
    
    state.dispose();
  });

  testWidgets('offline: cached events and inbox still render',
      (tester) async {
    final state = await makeStateWithPrefs(
      RequestLog(),
      offline: true,
      prefs: {
        SettingsService.keyDashboardCache: jsonEncode(dashboardJson()),
        SettingsService.keyEventsCache: jsonEncode(eventsJson()),
        SettingsService.keyInboxCache:
            jsonEncode(inboxJson()['items']),
        SettingsService.keyPlanCache: jsonEncode(planJson()),
      },
    );
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();
    expect(find.textContaining('OFFLINE'), findsOneWidget);

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Events').last);
    await tester.pumpAndSettle();
    expect(find.text('Deep work'), findsOneWidget);

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quick Capture').last);
    await tester.pumpAndSettle();
    expect(find.text('Buy milk'), findsOneWidget);

    expect(tester.takeException(), isNull);
    state.dispose();
  });

  testWidgets('today header greets by the injected time', (tester) async {
    final state = await makeState(RequestLog());
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PlanningScreen(
            state: state, now: () => DateTime(2026, 7, 21, 9, 0)),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Good Morning.'), findsOneWidget);
    state.dispose();

    final evening = await makeState(RequestLog());
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PlanningScreen(
            state: evening, now: () => DateTime(2026, 7, 21, 20, 0)),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Good Evening.'), findsOneWidget);
    evening.dispose();
  });

  testWidgets(
      'today header focus: running event with progress and next reasons',
      (tester) async {
    tester.view.physicalSize = const Size(800, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final state =
        await makeStateWithPrefs(RequestLog(), events: timelineEventsJson());
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PlanningScreen(
            state: state, now: () => DateTime(2026, 7, 21, 9, 0)),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text("TODAY'S FOCUS"), findsOneWidget);
    expect(find.text('Review PRs'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.textContaining('30 min left'), findsOneWidget);
    // Up next: the 10:00 entry with the scheduler's reasons as bullets.
    expect(find.text('UP NEXT'), findsOneWidget);
    expect(find.text('Recommended because:'), findsOneWidget);
    expect(find.text('• Highest priority'), findsOneWidget);
    expect(find.text('• energy is fresh'), findsOneWidget);
    state.dispose();
  });

  testWidgets('today header focus: next planned entry with countdown',
      (tester) async {
    final state = await makeState(RequestLog()); // events: only e1 (Ready)
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PlanningScreen(
            state: state, now: () => DateTime(2026, 7, 21, 9, 30)),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Deep work — starts in 30 min'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNothing);
    state.dispose();
  });

  testWidgets('bottom bar Capture destination lands focused in the input',
      (tester) async {
    tester.view.physicalSize = const Size(500, 800); // narrow -> bottom bar
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final state = await makeState(RequestLog());
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Capture'));
    await tester.pumpAndSettle();

    final editable =
        tester.widget<EditableText>(find.byType(EditableText).first);
    expect(editable.focusNode.hasFocus, isTrue,
        reason: 'one tap on Capture must land ready to type');
    state.dispose();
  });

  testWidgets('offline with no cache shows empty states, never crashes',
      (tester) async {
    final state = await makeStateWithPrefs(RequestLog(), offline: true);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quick Capture').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('Unable to connect to backend.'), findsOneWidget);
    expect(tester.takeException(), isNull);
    state.dispose();
  });

  testWidgets('planning: AI proposal loading states, timeout dialog, and cancellation',
      (tester) async {
    final log = RequestLog();
    final completer = Completer<http.Response>();

    final mockHttpClient = MockClient((request) async {
      log.requests.add('${request.method} ${request.url.path}');
      if (request.url.path == '/status') {
        return http.Response(jsonEncode({'status': 'ok'}), 200);
      }
      if (request.method == 'POST' || request.method == 'PUT') {
        log.bodies.add(request.body);
      }
      return completer.future;
    });

    SharedPreferences.setMockInitialValues({});
    final store = SettingsService(await SharedPreferences.getInstance());
    final settings = store.read().copyWith(aiTimeoutSeconds: 10);
    await store.write(settings);

    final state = AppState(store, clientFactory: (url) {
      return ApiClient(url,
          client: mockHttpClient,
          timeout: const Duration(seconds: 30),
          aiTimeoutSetting: const Duration(seconds: 30));
    });

    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();

    // Type a prompt and plan it
    await tester.enterText(find.byType(TextField).first, 'test long running AI');
    await tester.tap(find.text('Plan it'));
    await tester.pump(); // allow UI to update
    await tester.pump(const Duration(milliseconds: 100));
    // 1. Immediately: "Connecting..."
    expect(find.text('Connecting...'), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField).first).enabled, isFalse);

    // 2. Advance by 2 seconds: "Analyzing your request..."
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Analyzing your request...'), findsOneWidget);

    // 3. Advance by 6 seconds (total 8s): "Generating plan..."
    await tester.pump(const Duration(seconds: 6));
    expect(find.text('Generating plan...'), findsOneWidget);

    // 4. Advance by 2 seconds (total 10s) -> timeout dialog triggers
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Still waiting for the local AI'), findsOneWidget);

    // 5. Click "Continue Waiting"
    await tester.tap(find.text('Continue Waiting'));
    await tester.pump();
    expect(find.text('Still waiting for the local AI'), findsNothing);

    // 6. Advance by 6 seconds (total 16s): "Still thinking..."
    await tester.pump(const Duration(seconds: 6));
    expect(find.textContaining('Still thinking...'), findsOneWidget);

    // 7. Advance by 4 seconds (total 20s, another 10s dialog step) -> timeout triggers again
    await tester.pump(const Duration(seconds: 4));
    expect(find.text('Still waiting for the local AI'), findsOneWidget);

    // 8. Click "Cancel" to abort
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    // Controls should be re-enabled
    expect(find.text('Still waiting for the local AI'), findsNothing);
    expect(tester.widget<TextField>(find.byType(TextField).first).enabled, isTrue);

    // Clean up
    completer.complete(http.Response('{}', 200));
    state.dispose();
  });
}
