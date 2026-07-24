// PAIOS Mobile Companion (Milestone 20).
//
// The phone is only a client: every byte on screen comes from the REST
// API; every button calls exactly one endpoint. No scheduling, no
// learning, no reasoning, no domain state on the device.
//
// Navigation is adaptive: a bottom NavigationBar with the five primary
// destinations on narrow screens, a NavigationRail on wide screens; the
// drawer always carries the full list.
import 'package:flutter/material.dart';

import 'screens/assistant_screen.dart';
import 'screens/contexts_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/events_screen.dart';
import 'screens/goals_screen.dart';
import 'screens/inbox_screen.dart';
import 'screens/journal_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/planning_screen.dart';
import 'screens/projects_screen.dart';
import 'screens/recommendations_screen.dart';
import 'screens/reflections_screen.dart';
import 'screens/resources_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/study_screen.dart';
import 'screens/timeline_screen.dart';
import 'services/app_state.dart';
import 'services/connection_manager.dart';
import 'services/settings_service.dart';
import 'theme/app_theme.dart';
import 'widgets/offline_banner.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final store = await SettingsService.load();
  runApp(PaiosApp(
    state: AppState(
      store,
      // Production: auto-select LAN -> Relay -> Offline with no user
      // action. Tests inject a client factory and leave this off.
      connectionResolver: (settings) => ConnectionManager(
        lanUrl: settings.baseUrl,
        relayUrl: settings.relayUrl.isEmpty ? null : settings.relayUrl,
        account: settings.account,
        deviceToken: settings.deviceToken,
      ).resolve(),
    ),
  ));
}

class PaiosApp extends StatelessWidget {
  final AppState state;
  final bool startPolling;

  const PaiosApp({super.key, required this.state, this.startPolling = true});

  @override
  Widget build(BuildContext context) {
    // Listens to the THEME, not to the whole AppState. Watching AppState
    // here rebuilt MaterialApp — the application root — on every poll
    // tick and every notification, for a value that changes only when
    // the user flips the switch.
    return ValueListenableBuilder<bool>(
      valueListenable: state.darkTheme,
      builder: (context, dark, child) => MaterialApp(
        title: 'PAIOS',
        debugShowCheckedModeBanner: false,
        theme: lightTheme(),
        darkTheme: darkThemeData(),
        themeMode: dark ? ThemeMode.dark : ThemeMode.light,
        home: child,
      ),
      child: HomeShell(state: state, startPolling: startPolling),
    );
  }
}

class _Destination {
  final String title;
  final IconData icon;
  final Widget Function(AppState state) build;
  final String? _short; // compact label for the bar/rail
  const _Destination(this.title, this.icon, this.build, {String? short})
      : _short = short;

  String get shortLabel => _short ?? title;
}

// Deliberate: the list is the app's internal navigation registry,
// shared with the test suite.
// ignore: library_private_types_in_public_api
final List<_Destination> destinations = [
  _Destination('Today', Icons.today_outlined,
      (s) => PlanningScreen(state: s)),
  _Destination('Timeline', Icons.view_timeline_outlined,
      (s) => TimelineScreen(state: s)),
  _Destination('Quick Capture', Icons.inbox_outlined,
      (s) => InboxScreen(state: s), short: 'Capture'),
  _Destination('Dashboard', Icons.dashboard_outlined,
      (s) => DashboardScreen(state: s)),
  // M21: mobile companion screens (paired-device /mobile namespace).
  _Destination('Daily Journal', Icons.menu_book_outlined,
      (s) => JournalScreen(state: s), short: 'Journal'),
  _Destination('Study', Icons.school_outlined, (s) => StudyScreen(state: s)),
  _Destination('AI Assistant', Icons.smart_toy_outlined,
      (s) => AssistantScreen(state: s), short: 'Assistant'),
  _Destination('Recommendations', Icons.lightbulb_outline,
      (s) => RecommendationsScreen(state: s)),
  _Destination('Events', Icons.play_circle_outline,
      (s) => EventsScreen(state: s)),
  _Destination('Goals', Icons.flag_outlined, (s) => GoalsScreen(state: s)),
  _Destination(
      'Projects', Icons.folder_outlined, (s) => ProjectsScreen(state: s)),
  _Destination(
      'Contexts', Icons.place_outlined, (s) => ContextsScreen(state: s)),
  _Destination('Resources', Icons.battery_charging_full_outlined,
      (s) => ResourcesScreen(state: s)),
  _Destination('Reflections', Icons.psychology_outlined,
      (s) => ReflectionsScreen(state: s)),
  _Destination('Notifications', Icons.notifications_outlined,
      (s) => NotificationsScreen(state: s)),
  _Destination(
      'Settings', Icons.settings_outlined, (s) => SettingsScreen(state: s)),
];

/// The bottom bar / rail shows these; everything else lives behind
/// "More" (narrow) or the drawer (wide).
const int primaryCount = 4; // Today, Timeline, Capture, Dashboard

int get notificationsIndex =>
    destinations.indexWhere((d) => d.title == 'Notifications');

class HomeShell extends StatefulWidget {
  final AppState state;
  final bool startPolling;

  const HomeShell({super.key, required this.state, this.startPolling = true});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    widget.state.refresh();
    if (widget.startPolling) widget.state.startPolling();
  }

  void _select(int index) => setState(() => _index = index);

  Future<void> _showMoreSheet(BuildContext context) async {
    final picked = await showModalBottomSheet<int>(
      context: context,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (var i = primaryCount; i < destinations.length; i++)
              ListTile(
                selected: i == _index,
                leading: Icon(destinations[i].icon),
                title: Text(destinations[i].title),
                onTap: () => Navigator.pop(context, i),
              ),
          ],
        ),
      ),
    );
    if (picked != null) _select(picked);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final destination = destinations[_index];
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        final wide = MediaQuery.of(context).size.width >= 600;
        final unread = state.center.unreadCount;
        final page = Column(
          children: [
            OfflineBanner(
              visible: state.online == false,
              retrySeconds: state.settings.refreshSeconds,
            ),
            if (state.online == true &&
                state.connectionMode == ConnectionMode.remote)
              Container(
                width: double.infinity,
                color: Theme.of(context).colorScheme.primaryContainer,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: Row(
                  children: [
                    Icon(Icons.cloud_done_outlined,
                        size: 15,
                        color:
                            Theme.of(context).colorScheme.onPrimaryContainer),
                    const SizedBox(width: 6),
                    Text(
                      ConnectionMode.remote.label,
                      style: TextStyle(
                        color:
                            Theme.of(context).colorScheme.onPrimaryContainer,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                switchInCurve: Curves.easeOut,
                switchOutCurve: Curves.easeIn,
                child: KeyedSubtree(
                  key: ValueKey<int>(_index),
                  child: destination.build(state),
                ),
              ),
            ),
          ],
        );
        return Scaffold(
          appBar: AppBar(
            title: Text(destination.title),
            actions: [
              IconButton(
                tooltip: 'Notifications',
                onPressed: () => _select(notificationsIndex),
                icon: _BadgeIcon(unread: unread),
              ),
              IconButton(
                tooltip: 'Refresh',
                onPressed: state.refresh,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          drawer: Drawer(
            child: SafeArea(
              child: ListView(
                children: [
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('PAIOS',
                        style: TextStyle(
                            fontSize: 22, fontWeight: FontWeight.bold)),
                  ),
                  for (var i = 0; i < destinations.length; i++)
                    ListTile(
                      selected: i == _index,
                      leading: Icon(destinations[i].icon),
                      title: Text(destinations[i].title == 'Notifications' &&
                              unread > 0
                          ? 'Notifications ($unread)'
                          : destinations[i].title),
                      onTap: () {
                        _select(i);
                        Navigator.pop(context);
                      },
                    ),
                ],
              ),
            ),
          ),
          body: wide
              ? Row(
                  children: [
                    NavigationRail(
                      selectedIndex: _index < primaryCount ? _index : null,
                      labelType: NavigationRailLabelType.all,
                      onDestinationSelected: _select,
                      destinations: [
                        for (var i = 0; i < primaryCount; i++)
                          NavigationRailDestination(
                            icon: Icon(destinations[i].icon),
                            label: Text(destinations[i].shortLabel),
                          ),
                      ],
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(child: page),
                  ],
                )
              : page,
          bottomNavigationBar: wide
              ? null
              : NavigationBar(
                  selectedIndex:
                      _index < primaryCount ? _index : primaryCount,
                  onDestinationSelected: (index) => index < primaryCount
                      ? _select(index)
                      : _showMoreSheet(context),
                  destinations: [
                    for (var i = 0; i < primaryCount; i++)
                      NavigationDestination(
                        icon: Icon(destinations[i].icon),
                        label: destinations[i].shortLabel,
                      ),
                    const NavigationDestination(
                      icon: Icon(Icons.more_horiz),
                      label: 'More',
                    ),
                  ],
                ),
        );
      },
    );
  }
}

class _BadgeIcon extends StatelessWidget {
  final int unread;
  const _BadgeIcon({required this.unread});

  @override
  Widget build(BuildContext context) {
    final icon = Icon(unread > 0
        ? Icons.notifications_active_outlined
        : Icons.notifications_outlined);
    if (unread == 0) return icon;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        icon,
        Positioned(
          right: -6,
          top: -4,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.error,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text('$unread',
                style: const TextStyle(fontSize: 10, color: Colors.white)),
          ),
        ),
      ],
    );
  }
}
