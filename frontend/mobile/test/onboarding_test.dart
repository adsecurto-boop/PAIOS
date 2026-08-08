import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:paios_mobile/screens/onboarding_screen.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/onboarding_service.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Onboarding Unit Tests', () {
    test('Settings read and write', () async {
      SharedPreferences.setMockInitialValues({'onboarding_completed': true});
      final service = await SettingsService.load();
      final settings = service.read();
      expect(settings.onboardingCompleted, isTrue);

      final next = settings.copyWith(onboardingCompleted: false);
      await service.write(next);
      final updated = service.read();
      expect(updated.onboardingCompleted, isFalse);
    });

    test('OnboardingAiEngine responds to various goals', () {
      final engine = OnboardingAiEngine();
      final init = engine.getInitialResponse();
      expect(init.options, contains('Study'));

      final studyRes = engine.respondToGoal('Study');
      expect(studyRes.targetAction, equals('createProject'));
      expect(studyRes.actionRoute, equals('projects'));

      final exploringRes = engine.respondToGoal('Just Exploring');
      expect(exploringRes.targetAction, equals('createInboxItem'));
      expect(exploringRes.actionRoute, equals('capture'));
    });
  });

  group('OnboardingService State Machine Tests', () {
    late AppState appState;
    late SettingsService settingsService;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      settingsService = await SettingsService.load();
      final client = ApiClient('http://test', client: MockClient((req) async {
        if (req.url.path == '/projects') {
          return http.Response(jsonEncode({'projects': []}), 200);
        }
        if (req.url.path == '/inbox') {
          return http.Response(jsonEncode({'items': []}), 200);
        }
        return http.Response('{}', 404);
      }));
      appState = AppState(settingsService, clientFactory: (_) => client);
    });

    test('Initial welcome state', () {
      final onboarding = OnboardingService(appState);
      expect(onboarding.state.step, equals(OnboardingStep.welcome));
      expect(onboarding.state.history, isEmpty);
    });

    test('Start Setup advances step', () {
      final onboarding = OnboardingService(appState);
      onboarding.startSetup();
      expect(onboarding.state.step, equals(OnboardingStep.chatFlow));
      expect(onboarding.state.history.length, equals(1));
      expect(onboarding.state.history.first.isUser, isFalse);
      expect(onboarding.state.options, contains('Study'));
    });

    test('Select goal triggers AI recommendation', () async {
      final onboarding = OnboardingService(appState);
      onboarding.startSetup();
      await onboarding.selectGoal('Study');

      expect(onboarding.state.selectedGoal, equals('Study'));
      expect(onboarding.state.history.length, equals(3));
      expect(onboarding.state.targetAction, equals('createProject'));
      expect(onboarding.state.isWaitingForAction, isTrue);
    });

    test('Verify action fails when no changes made', () async {
      final onboarding = OnboardingService(appState);
      onboarding.startSetup();
      await onboarding.selectGoal('Study');
      await onboarding.verifyAction();

      expect(onboarding.state.history.last.text, contains("I couldn't verify"));
      expect(onboarding.state.targetAction, equals('createProject'));
      expect(onboarding.state.isWaitingForAction, isTrue);
    });

    test('Verify action succeeds when project count increases', () async {
      final projectsResponse = {'projects': <dynamic>[]};
      final client = ApiClient('http://test', client: MockClient((req) async {
        if (req.url.path == '/projects') {
          return http.Response(jsonEncode(projectsResponse), 200);
        }
        return http.Response('{}', 404);
      }));
      appState = AppState(settingsService, clientFactory: (_) => client);

      final projectsBefore = await appState.client.getProjects();
      expect(projectsBefore.length, 0);

      final onboarding = OnboardingService(appState);
      onboarding.startSetup();
      await onboarding.selectGoal('Study');

      expect(onboarding.state.initialProjectCount, 0);

      projectsResponse['projects'] = [
        {'project_id': 'p_new', 'name': 'Study Project', 'status': 'Active'}
      ];

      final projectsAfter = await appState.client.getProjects();
      expect(projectsAfter.length, 1);

      await onboarding.verifyAction();
      expect(onboarding.state.targetAction, isNull);
      expect(onboarding.state.isWaitingForAction, isFalse);
      expect(onboarding.state.history.last.text, contains("plan your day"));
      expect(onboarding.state.options, contains('Continue'));
    });
  });

  group('Onboarding UI Widgets', () {
    late AppState appState;
    late SettingsService settingsService;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      settingsService = await SettingsService.load();
      final client = ApiClient('http://test', client: MockClient((req) async {
        return http.Response('{"projects": [], "items": []}', 200);
      }));
      appState = AppState(settingsService, clientFactory: (_) => client);
    });

    testWidgets('Welcome view buttons trigger setup/skip', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: OnboardingFlowScreen(state: appState),
      ));

      expect(find.text('Welcome to PAIOS'), findsOneWidget);
      expect(find.text('Start Setup'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);

      await tester.ensureVisible(find.text('Skip'));
      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();
      expect(appState.onboardingCompleted.value, isTrue);
    });

    testWidgets('Chat view goal selection', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: OnboardingFlowScreen(state: appState),
      ));

      await tester.ensureVisible(find.text('Start Setup'));
      await tester.tap(find.text('Start Setup'));
      await tester.pumpAndSettle();

      expect(find.text('PAIOS Onboarding'), findsOneWidget);
      expect(find.text('Great. Before we begin, what brings you here?'), findsOneWidget);
      expect(find.text('Study'), findsOneWidget);

      await tester.tap(find.text('Study'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Study'), findsOneWidget);
    });
  });
}
