// The staged connection check behind Settings -> "Test connection".
//
// One button used to mean one call, and every failure of that call was
// rendered as "Offline". Three different things can be wrong, and the
// user can only act on the one that is:
//
//   1. the desktop is not answering at all         (start PAIOS / Wi-Fi)
//   2. the desktop answers but the pairing is dead (pair again)
//   3. the desktop and pairing are fine, the AI is not (desktop Settings)
//
// So the check walks the real chain and names the link that broke:
//
//     phone -> desktop backend -> pairing -> desktop AI -> Ollama
//
// Note the direction. The phone asks the DESKTOP for an AI answer
// (/mobile/assistant/query); it never speaks to Ollama, and there is no
// code path here that could.
import 'api_client.dart';

enum CheckStatus { ok, warning, failed }

class CheckStep {
  final String name;
  final CheckStatus status;
  final String detail;
  const CheckStep(this.name, this.status, this.detail);

  bool get ok => status == CheckStatus.ok;
}

class ConnectionReport {
  final List<CheckStep> steps;
  const ConnectionReport(this.steps);

  bool get connected => steps.isNotEmpty && steps.every((s) => s.ok);

  /// The first thing that is not right — what the snackbar should say.
  CheckStep? get firstProblem {
    for (final step in steps) {
      if (!step.ok) return step;
    }
    return null;
  }

  String get summary {
    final problem = firstProblem;
    if (problem == null) {
      return 'Connected — desktop, pairing and AI all answered.';
    }
    return '${problem.name}: ${problem.detail}';
  }
}

/// Runs the chain, reporting each stage through [onStage] as it starts.
///
/// Never throws: every failure becomes a [CheckStep] carrying the real
/// error text. The walk stops at the first hard failure, because the
/// later stages cannot mean anything once an earlier link is broken.
Future<ConnectionReport> checkConnection(
  ApiClient client, {
  String? deviceToken,
  void Function(String stage)? onStage,
}) async {
  final steps = <CheckStep>[];

  onStage?.call('Connecting to your desktop…');
  try {
    final status = await client.getStatus();
    final operational = status['operational'] == true;
    steps.add(CheckStep(
      'Desktop',
      operational ? CheckStatus.ok : CheckStatus.warning,
      operational
          ? 'answered at ${client.baseUrl} (state: ${status['state']})'
          : 'answered at ${client.baseUrl} but is still starting up'
              ' (state: ${status['state']})',
    ));
    if (!operational) return ConnectionReport(steps);
  } on ApiTimeoutException catch (error) {
    steps.add(CheckStep('Desktop', CheckStatus.failed,
        'reached ${client.baseUrl} but got no reply in'
        ' ${error.waited.inSeconds}s'));
    return ConnectionReport(steps);
  } on ApiUnreachableException catch (error) {
    steps.add(CheckStep('Desktop', CheckStatus.failed,
        'could not reach ${client.baseUrl} — ${error.detail}'));
    return ConnectionReport(steps);
  } on ApiResponseException catch (error) {
    steps.add(CheckStep('Desktop', CheckStatus.failed,
        'answered HTTP ${error.status} (${error.errorType}):'
        ' ${error.message}'));
    return ConnectionReport(steps);
  }

  onStage?.call('Checking this device is still paired…');
  if (deviceToken == null || deviceToken.isEmpty) {
    steps.add(const CheckStep('Pairing', CheckStatus.failed,
        'this device is not paired — enter the desktop code above'));
    return ConnectionReport(steps);
  }
  try {
    final result = await client.validateToken(deviceToken);
    if (result['valid'] != true) {
      steps.add(const CheckStep('Pairing', CheckStatus.failed,
          'the desktop did not confirm this device'));
      return ConnectionReport(steps);
    }
    steps.add(CheckStep(
        'Pairing', CheckStatus.ok, 'valid (${result['device_id']})'));
  } on ApiResponseException catch (error) {
    steps.add(CheckStep(
        'Pairing',
        CheckStatus.failed,
        error.status == 401
            ? 'the desktop revoked this device — forget the pairing and'
                ' pair again'
            : '${error.errorType}: ${error.message}'));
    return ConnectionReport(steps);
  } on ApiUnreachableException catch (error) {
    steps.add(CheckStep('Pairing', CheckStatus.failed, error.detail));
    return ConnectionReport(steps);
  }

  onStage?.call('Asking your desktop AI to answer '
      '(the first answer can take a minute)…');
  try {
    final answer = await client.assistantQuery(
        'Reply with one short sentence confirming you are reachable.');
    final source = answer['source'] as String? ?? 'heuristic';
    final text = (answer['answer'] as String? ?? '').trim();
    if (source == 'heuristic') {
      // Not a failure: PAIOS answers deterministically by design when
      // no model is configured. Say which one answered.
      steps.add(const CheckStep(
          'AI',
          CheckStatus.warning,
          'the desktop has no AI provider switched on, so it answered'
              ' deterministically. Turn one on in desktop Settings →'
              ' Intelligence.'));
    } else {
      steps.add(CheckStep('AI', CheckStatus.ok,
          'the desktop model answered — "${_clip(text)}"'));
    }
  } on ApiTimeoutException catch (error) {
    steps.add(CheckStep(
        'AI',
        CheckStatus.failed,
        'the desktop is up but the model sent nothing within'
            ' ${error.waited.inSeconds}s — it may still be loading'));
  } on ApiResponseException catch (error) {
    steps.add(CheckStep('AI', CheckStatus.failed,
        'HTTP ${error.status} (${error.errorType}): ${error.message}'));
  } on ApiUnreachableException catch (error) {
    steps.add(CheckStep('AI', CheckStatus.failed, error.detail));
  }
  return ConnectionReport(steps);
}

String _clip(String text, [int limit = 80]) =>
    text.length <= limit ? text : '${text.substring(0, limit)}…';
