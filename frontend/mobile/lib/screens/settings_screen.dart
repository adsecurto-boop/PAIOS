// Settings: backend URL (never hardcoded elsewhere), refresh interval,
// dark theme, device pairing (M21), About.
//
// Every button here reports what it did. A press that changes stored
// state must be visibly acknowledged - busy while it works, then the
// outcome in the user's words - because a silent button is
// indistinguishable from a broken one.
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/connection_check.dart';
import '../services/pairing_payload.dart';

const List<int> refreshChoices = [2, 5, 10, 30, 60];

/// Rejects an address before it is stored, and says why.
///
/// Returns null when [text] is usable. The check is deliberately the
/// same shape as [ApiClient.normalizeUrl]: whatever passes here is what
/// the client will actually dial.
String? validateServerUrl(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) {
    return 'Enter your desktop address, for example 192.168.1.15:8765';
  }
  if (trimmed.contains(' ')) return 'An address cannot contain spaces.';
  final Uri uri;
  try {
    uri = Uri.parse(ApiClient.normalizeUrl(trimmed));
  } on FormatException {
    return 'That is not a valid address.';
  }
  if (uri.host.isEmpty) {
    return 'That address has no computer name or IP.';
  }
  if (uri.hasPort && (uri.port < 1 || uri.port > 65535)) {
    return 'The port must be between 1 and 65535.';
  }
  return null;
}

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

  // --- Server card state (Problem 1: the silent Save button) -----------
  bool _savingServer = false;
  String? _serverError; // inline validation, shown under the field
  String? _serverNotice; // "Saving…" / "Saved — connected to …"
  bool _serverNoticeIsError = false;

  // --- Test-connection state ------------------------------------------
  bool _testing = false;
  String? _testStage;
  ConnectionReport? _testReport;

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

  /// The "Save server" button, end to end.
  ///
  /// Validate -> show busy -> persist -> re-check -> report. Every one of
  /// those steps is visible; the press is never a no-op on screen. It
  /// used to call [AppState.updateSettings] and show nothing at all,
  /// while that call spent up to twelve seconds probing the network.
  Future<void> _saveServer() async {
    if (_savingServer) return;
    final typed = _urlController.text;
    final problem = validateServerUrl(typed);
    if (problem != null) {
      setState(() {
        _serverError = problem;
        _serverNotice = null;
      });
      _notify(problem);
      return;
    }
    final normalized = ApiClient.normalizeUrl(typed);
    setState(() {
      _savingServer = true;
      _serverError = null;
      _serverNoticeIsError = false;
      _serverNotice = 'Saving…';
      _urlController.text = normalized;
    });
    final result = await widget.state.updateSettings(
        widget.state.settings.copyWith(baseUrl: normalized));
    if (!mounted) return;
    setState(() {
      _savingServer = false;
      _serverNotice = result.message;
      _serverNoticeIsError = !result.saved || !result.reachable;
    });
    _notify(result.message);
  }

  Future<void> _saveRemote() async {
    final result = await widget.state.updateSettings(
        widget.state.settings.copyWith(relayUrl: _relayController.text.trim()));
    if (!mounted) return;
    setState(() {});
    _notify(_relayController.text.trim().isEmpty
        ? 'Remote access off — the phone uses Wi-Fi only.'
        : 'Remote access saved. ${result.message}');
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

  /// Walks the real chain — desktop, pairing, desktop AI — and shows
  /// each stage as it runs.
  ///
  /// This is the button that used to answer "Offline" for a desktop that
  /// was up: it made one short call and rendered every failure of it,
  /// including a slow model, as an outage. Now each link reports for
  /// itself and the AI stage gets the deadline an AI actually needs.
  Future<void> _testConnection() async {
    if (_testing) return;
    setState(() {
      _testing = true;
      _testReport = null;
      _testStage = 'Starting…';
    });
    final report = await checkConnection(
      widget.state.client,
      deviceToken: widget.state.settings.deviceToken,
      onStage: (stage) {
        if (mounted) setState(() => _testStage = stage);
      },
    );
    if (!mounted) return;
    setState(() {
      _testing = false;
      _testStage = null;
      _testReport = report;
    });
    _notify(report.summary);
  }

  Future<void> _forgetPairing() async {
    await widget.state.updateSettings(widget.state.settings
        .copyWith(clearToken: true, deviceName: ''));
    if (mounted) setState(() {});
    _notify('Pairing forgotten — journal, study and assistant need'
        ' a new code.');
  }

  /// The live narration while the check runs, then one line per link.
  Widget _buildTestPanel(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final small = Theme.of(context).textTheme.bodySmall;
    if (_testStage != null) {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 8),
            Expanded(child: Text(_testStage!, style: small)),
          ],
        ),
      );
    }
    final report = _testReport;
    if (report == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final step in report.steps)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    switch (step.status) {
                      CheckStatus.ok => Icons.check_circle_outline,
                      CheckStatus.warning => Icons.info_outline,
                      CheckStatus.failed => Icons.cancel_outlined,
                    },
                    size: 16,
                    color: switch (step.status) {
                      CheckStatus.ok => scheme.primary,
                      CheckStatus.warning => scheme.tertiary,
                      CheckStatus.failed => scheme.error,
                    },
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text('${step.name} — ${step.detail}',
                        style: small),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
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
                  enabled: !_savingServer,
                  onSubmitted: (_) => _saveServer(),
                  onChanged: (_) {
                    if (_serverError != null) {
                      setState(() => _serverError = null);
                    }
                  },
                  decoration: InputDecoration(
                    labelText: 'Backend URL',
                    hintText: 'http://192.168.1.15:8765',
                    border: const OutlineInputBorder(),
                    errorText: _serverError,
                  ),
                ),
                if (_serverNotice != null) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(
                        _savingServer
                            ? Icons.sync
                            : _serverNoticeIsError
                                ? Icons.error_outline
                                : Icons.check_circle_outline,
                        size: 16,
                        color: _serverNoticeIsError
                            ? Theme.of(context).colorScheme.error
                            : Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          _serverNotice!,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                                  color: _serverNoticeIsError
                                      ? Theme.of(context).colorScheme.error
                                      : null),
                        ),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton(
                    onPressed: _savingServer ? null : _saveServer,
                    child: _savingServer
                        ? const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2),
                              ),
                              SizedBox(width: 8),
                              Text('Saving…'),
                            ],
                          )
                        : const Text('Save server'),
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
                        onPressed: _testing ? null : _forgetPairing,
                        child: const Text('Forget pairing'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: _testing ? null : _testConnection,
                        child: _testing
                            ? const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2),
                                  ),
                                  SizedBox(width: 8),
                                  Text('Testing…'),
                                ],
                              )
                            : const Text('Test connection'),
                      ),
                    ],
                  ),
                  _buildTestPanel(context),
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
