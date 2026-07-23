// Settings: backend URL (never hardcoded elsewhere), refresh interval,
// dark theme, device pairing (M21), About.
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/pairing_payload.dart';

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
  late final TextEditingController _relayController;
  late final TextEditingController _pasteController;
  bool _pairing = false;

  @override
  void initState() {
    super.initState();
    _urlController =
        TextEditingController(text: widget.state.settings.baseUrl);
    _deviceNameController.text = widget.state.settings.deviceName;
    _relayController =
        TextEditingController(text: widget.state.settings.relayUrl);
    _pasteController = TextEditingController();
  }

  @override
  void dispose() {
    _urlController.dispose();
    _codeController.dispose();
    _deviceNameController.dispose();
    _relayController.dispose();
    _pasteController.dispose();
    super.dispose();
  }

  Future<void> _save({String? url, int? refresh, bool? dark}) async {
    await widget.state.updateSettings(widget.state.settings.copyWith(
      baseUrl: url,
      refreshSeconds: refresh,
      darkTheme: dark,
    ));
    if (mounted) setState(() {});
  }

  Future<void> _saveRemote() async {
    await widget.state.updateSettings(
        widget.state.settings.copyWith(relayUrl: _relayController.text.trim()));
    if (mounted) setState(() {});
    _notify(_relayController.text.trim().isEmpty
        ? 'Remote access off — the phone uses Wi-Fi only.'
        : 'Remote access saved — the phone can reach PAIOS anywhere.');
  }

  /// Reads a pasted/scanned `paios://pair` payload (or a plain address)
  /// and fills the server + relay fields so the user does not type them.
  void _applyPastedPayload() {
    final payload = PairingPayload.parse(_pasteController.text);
    if (!payload.isUsable) {
      _notify("That code wasn't recognised — check it and try again.");
      return;
    }
    setState(() {
      if (payload.hasLan) _urlController.text = payload.lanUrl!;
      if (payload.hasRelay) _relayController.text = payload.relayUrl!;
    });
    widget.state.updateSettings(widget.state.settings.copyWith(
      baseUrl: payload.hasLan ? payload.lanUrl : null,
      relayUrl: payload.hasRelay ? payload.relayUrl : null,
      account: payload.account,
    ));
    _pasteController.clear();
    _notify('Connection details filled in — now enter the pairing code.');
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
      await widget.state.updateSettings(widget.state.settings.copyWith(
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
    await widget.state.updateSettings(widget.state.settings
        .copyWith(clearToken: true, deviceName: ''));
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
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Use PAIOS anywhere (optional)'),
                const SizedBox(height: 4),
                Text(
                  'Paste the connection code from the desktop to fill these'
                  ' in automatically, or enter the relay address your'
                  ' desktop is set up with. Then PAIOS works on mobile data'
                  ' too, not just this Wi-Fi.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.outline),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _pasteController,
                        decoration: const InputDecoration(
                          labelText: 'Paste connection code',
                          hintText: 'paios://pair?…  (or an address)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed: _applyPastedPayload,
                      child: const Text('Use'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _relayController,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'Relay address (optional)',
                    hintText: 'https://relay.example.com',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton(
                    onPressed: _saveRemote,
                    child: const Text('Save remote access'),
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
            'PAIOS companion 1.1.0\n'
            'Your PAIOS lives on your computer. This app is a window into '
            'it — from your Wi-Fi or anywhere through secure remote access.',
          ),
        ),
      ],
    );
  }
}
