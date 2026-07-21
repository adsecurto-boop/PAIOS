// PAIOS Mobile Companion (Milestone 15).
//
// The phone is only a client: every byte on screen comes from the REST
// API; every button calls exactly one endpoint. No scheduling, no
// learning, no reasoning, no domain state on the device.
import 'package:flutter/material.dart';

import 'screens/contexts_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/events_screen.dart';
import 'screens/goals_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/projects_screen.dart';
import 'screens/recommendations_screen.dart';
import 'screens/reflections_screen.dart';
import 'screens/resources_screen.dart';
import 'screens/settings_screen.dart';
import 'services/app_state.dart';
import 'services/settings_service.dart';
import 'theme/app_theme.dart';
import 'widgets/offline_banner.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final store = await SettingsService.load();
  runApp(PaiosApp(state: AppState(store)));
}

class PaiosApp extends StatelessWidget {
  final AppState state;
  final bool startPolling;

  const PaiosApp({super.key, required this.state, this.startPolling = true});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) => MaterialApp(
        title: 'PAIOS',
        debugShowCheckedModeBanner: false,
        theme: lightTheme(),
        darkTheme: darkTheme(),
        themeMode:
            state.settings.darkTheme ? ThemeMode.dark : ThemeMode.light,
        home: HomeShell(state: state, startPolling: startPolling),
      ),
    );
  }
}

class _Destination {
  final String title;
  final IconData icon;
  final Widget Function(AppState state) build;
  const _Destination(this.title, this.icon, this.build);
}

final List<_Destination> destinations = [
  _Destination('Dashboard', Icons.dashboard_outlined,
      (s) => DashboardScreen(state: s)),
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

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final destination = destinations[_index];
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        final unread = state.center.unreadCount;
        return Scaffold(
          appBar: AppBar(
            title: Text(destination.title),
            actions: [
              IconButton(
                tooltip: 'Notifications',
                onPressed: () => setState(() => _index = 8),
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
                        setState(() => _index = i);
                        Navigator.pop(context);
                      },
                    ),
                ],
              ),
            ),
          ),
          body: Column(
            children: [
              OfflineBanner(
                visible: state.online == false,
                retrySeconds: state.settings.refreshSeconds,
              ),
              Expanded(child: destination.build(state)),
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
