// Golden UI screenshots. Seed/update the baselines with:
//
//   flutter test --update-goldens test/golden_test.dart
//
// Afterwards a plain `flutter test` compares pixel-for-pixel.
import 'dart:convert';
import 'dart:ui' show Size;

import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/main.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fixtures.dart';
import 'widget_test.dart' show mockFactory, RequestLog;

void main() {
  Future<AppState> stateWithData({bool offline = false}) async {
    SharedPreferences.setMockInitialValues({
      if (offline)
        SettingsService.keyDashboardCache: jsonEncode(dashboardJson()),
    });
    final store = SettingsService(await SharedPreferences.getInstance());
    return AppState(store,
        clientFactory: mockFactory(RequestLog(), offline: offline));
  }

  testWidgets('golden: dashboard (dark)', (tester) async {
    tester.view.physicalSize = const Size(1080, 2280);
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    final state = await stateWithData();
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();
    // M20: Planning boots first; the golden is still the dashboard.
    await tester.tap(find.text('Dashboard').last);
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(PaiosApp),
      matchesGoldenFile('goldens/dashboard_dark.png'),
    );
    state.dispose();
  });

  testWidgets('golden: dashboard offline banner', (tester) async {
    tester.view.physicalSize = const Size(1080, 2280);
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    final state = await stateWithData(offline: true);
    await tester.pumpWidget(PaiosApp(state: state, startPolling: false));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Dashboard').last);
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(PaiosApp),
      matchesGoldenFile('goldens/dashboard_offline.png'),
    );
    state.dispose();
  });
}
