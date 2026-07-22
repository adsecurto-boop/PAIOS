// AI Assistant (M21): a question box over POST /mobile/assistant/query.
// The conversation lives in memory only - the phone never stores
// dialogue. When the desktop has no AI provider the answer is
// deterministic and a subtle hint says so (never an error); while the
// app is offline the input is disabled with a clear message.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';

class _Exchange {
  final String question;
  AssistantAnswer? answer;
  String? errorText;
  _Exchange(this.question);
}

class AssistantScreen extends StatefulWidget {
  final AppState state;
  const AssistantScreen({super.key, required this.state});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final TextEditingController _input = TextEditingController();
  final List<_Exchange> _exchanges = [];
  bool _busy = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _ask() async {
    final text = _input.text.trim();
    if (text.isEmpty || _busy || widget.state.online == false) return;
    final exchange = _Exchange(text);
    setState(() {
      _busy = true;
      _exchanges.add(exchange);
    });
    _input.clear();
    try {
      final payload = await widget.state.client.assistantQuery(text);
      exchange.answer = AssistantAnswer.fromJson(payload);
    } on ApiUnreachableException catch (e) {
      exchange.errorText = 'Server unreachable: ${e.detail}';
    } on ApiResponseException catch (e) {
      exchange.errorText = e.status == 401
          ? 'Not paired — pair this device in Settings first.'
          : e.message;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final offline = widget.state.online == false;
    return Column(
      children: [
        Expanded(
          child: _exchanges.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'Ask about your day, plans or goals.\n'
                      'The desktop answers; the phone only asks.',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: theme.colorScheme.outline),
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: _exchanges.length,
                  itemBuilder: (context, index) =>
                      _bubble(context, _exchanges[index]),
                ),
        ),
        if (offline)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
            child: Text(
              'Offline — the assistant needs the desktop connection.',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.error),
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: TextField(
            controller: _input,
            enabled: !offline,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => _ask(),
            decoration: InputDecoration(
              hintText:
                  offline ? 'Unavailable offline' : 'Ask the assistant…',
              border: const OutlineInputBorder(),
              isDense: true,
              suffixIcon: _busy
                  ? const Padding(
                      padding: EdgeInsets.all(10),
                      child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2)),
                    )
                  : IconButton(
                      tooltip: 'Ask',
                      icon: const Icon(Icons.send),
                      onPressed: offline ? null : _ask,
                    ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _bubble(BuildContext context, _Exchange exchange) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final answer = exchange.answer;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: Card(
            color: scheme.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Text(exchange.question,
                  style: TextStyle(color: scheme.onPrimaryContainer)),
            ),
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: exchange.errorText != null
                  ? Text(exchange.errorText!,
                      style: TextStyle(color: scheme.error))
                  : answer == null
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(answer.answer),
                            for (final bullet in answer.bullets)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text('• $bullet'),
                              ),
                            if (answer.heuristic)
                              Padding(
                                padding: const EdgeInsets.only(top: 6),
                                child: Text(
                                  'Desktop AI is off — deterministic answer',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                      color: scheme.outline,
                                      fontStyle: FontStyle.italic),
                                ),
                              ),
                          ],
                        ),
            ),
          ),
        ),
      ],
    );
  }
}
