// Settings: backend URL (never hardcoded elsewhere), refresh interval,
// dark theme, About.
import 'package:flutter/material.dart';

import '../services/app_state.dart';
import '../services/settings_service.dart';

const List<int> refreshChoices = [2, 5, 10, 30, 60];

class SettingsScreen extends StatefulWidget {
  final AppState state;

  const SettingsScreen({super.key, required this.state});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController =
        TextEditingController(text: widget.state.settings.baseUrl);
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _save({String? url, int? refresh, bool? dark}) async {
    final current = widget.state.settings;
    await widget.state.updateSettings(Settings(
      baseUrl: url ?? current.baseUrl,
      refreshSeconds: refresh ?? current.refreshSeconds,
      darkTheme: dark ?? current.darkTheme,
    ));
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final settings = widget.state.settings;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Server'),
                const SizedBox(height: 8),
                TextField(
                  controller: _urlController,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'Backend URL',
                    hintText: 'http://192.168.1.15:8765',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton(
                    onPressed: () =>
                        _save(url: _urlController.text.trim()),
                    child: const Text('Save server'),
                  ),
                ),
              ],
            ),
          ),
        ),
        ListTile(
          title: const Text('Refresh interval'),
          trailing: DropdownButton<int>(
            value: refreshChoices.contains(settings.refreshSeconds)
                ? settings.refreshSeconds
                : refreshChoices[2],
            items: [
              for (final seconds in refreshChoices)
                DropdownMenuItem(value: seconds, child: Text('${seconds}s')),
            ],
            onChanged: (value) {
              if (value != null) _save(refresh: value);
            },
          ),
        ),
        SwitchListTile(
          title: const Text('Dark theme'),
          value: settings.darkTheme,
          onChanged: (value) => _save(dark: value),
        ),
        const Divider(),
        const ListTile(
          title: Text('About'),
          subtitle: Text(
            'PAIOS Mobile Companion 1.0.0 (Milestone 15)\n'
            'A REST-only remote client. The laptop remains the operating '
            'system; the phone never schedules, learns, reasons, or stores '
            'domain state.',
          ),
        ),
      ],
    );
  }
}
