// Settings: backend URL (never hardcoded elsewhere), refresh interval,
// dark theme, device pairing (M21), About.
import 'package:flutter/material.dart';

import '../services/api_client.dart';
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
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _deviceNameController = TextEditingController();
  bool _pairing = false;

  @override
  void initState() {
    super.initState();
    _urlController =
        TextEditingController(text: widget.state.settings.baseUrl);
    _deviceNameController.text = widget.state.settings.deviceName;
  }

  @override
  void dispose() {
    _urlController.dispose();
    _codeController.dispose();
    _deviceNameController.dispose();
    super.dispose();
  }

  Future<void> _save({String? url, int? refresh, bool? dark}) async {
    final current = widget.state.settings;
    await widget.state.updateSettings(Settings(
      baseUrl: url ?? current.baseUrl,
      refreshSeconds: refresh ?? current.refreshSeconds,
      darkTheme: dark ?? current.darkTheme,
      deviceToken: current.deviceToken,
      deviceName: current.deviceName,
    ));
    if (mounted) setState(() {});
  }

  void _notify(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // --- M21: device pairing ------------------------------------------------

  /// Exchanges the desktop's 6-digit code for the bearer token. The
  /// token is shown exactly once by the API, so it is stored right away.
  Future<void> _pair() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) {
      _notify('Enter the 6-digit code shown on the desktop.');
      return;
    }
    final name = _deviceNameController.text.trim();
    final deviceName = name.isEmpty ? 'PAIOS mobile' : name;
    setState(() => _pairing = true);
    try {
      final result =
          await widget.state.client.pairDevice(code, deviceName);
      final token = result['token'] as String? ?? '';
      if (token.isEmpty) {
        _notify('Pairing failed: the server sent no token.');
        return;
      }
      final current = widget.state.settings;
      await widget.state.updateSettings(Settings(
        baseUrl: current.baseUrl,
        refreshSeconds: current.refreshSeconds,
        darkTheme: current.darkTheme,
        deviceToken: token,
        deviceName: deviceName,
      ));
      _codeController.clear();
      _notify('Paired — the token is stored on this device.');
    } on ApiUnreachableException catch (e) {
      _notify('Server unreachable: ${e.detail}');
    } on ApiResponseException catch (e) {
      _notify(e.message);
    } finally {
      if (mounted) setState(() => _pairing = false);
    }
  }

  Future<void> _testPairing() async {
    final token = widget.state.settings.deviceToken;
    if (token == null) return;
    try {
      final result = await widget.state.client.validateToken(token);
      _notify(result['valid'] == true
          ? 'Pairing is valid (${result['device_id']}).'
          : 'The server did not confirm the token.');
    } on ApiUnreachableException catch (e) {
      _notify('Server unreachable: ${e.detail}');
    } on ApiResponseException catch (e) {
      _notify(e.status == 401
          ? 'Token rejected — it was revoked on the desktop.'
              ' Forget pairing and pair again.'
          : e.message);
    }
  }

  Future<void> _forgetPairing() async {
    final current = widget.state.settings;
    await widget.state.updateSettings(Settings(
      baseUrl: current.baseUrl,
      refreshSeconds: current.refreshSeconds,
      darkTheme: current.darkTheme,
      deviceToken: null,
      deviceName: '',
    ));
    if (mounted) setState(() {});
    _notify('Pairing forgotten — journal, study and assistant need'
        ' a new code.');
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
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Pair with desktop'),
                const SizedBox(height: 8),
                if (settings.deviceToken != null) ...[
                  Row(
                    children: [
                      Icon(Icons.verified_user_outlined,
                          size: 18,
                          color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text('Paired as '
                            '${settings.deviceName.isEmpty ? 'Mobile device' : settings.deviceName}'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: _forgetPairing,
                        child: const Text('Forget pairing'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: _testPairing,
                        child: const Text('Test connection'),
                      ),
                    ],
                  ),
                ] else ...[
                  Text(
                    'On the desktop, open PAIOS and start pairing to get'
                    ' a code. Pairing unlocks the journal, study and'
                    ' assistant screens.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _codeController,
                    keyboardType: TextInputType.number,
                    maxLength: 6,
                    decoration: const InputDecoration(
                      labelText: '6-digit pairing code',
                      counterText: '',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _deviceNameController,
                    decoration: const InputDecoration(
                      labelText: 'Device name (optional)',
                      hintText: 'e.g. My phone',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      onPressed: _pairing ? null : _pair,
                      child: const Text('Pair'),
                    ),
                  ),
                ],
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
