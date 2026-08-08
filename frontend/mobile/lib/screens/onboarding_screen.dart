import 'package:flutter/material.dart';
import '../services/app_state.dart';
import '../services/onboarding_service.dart';
import 'projects_screen.dart';
import 'inbox_screen.dart';
import 'planning_screen.dart';

class OnboardingFlowScreen extends StatefulWidget {
  final AppState state;

  const OnboardingFlowScreen({super.key, required this.state});

  @override
  State<OnboardingFlowScreen> createState() => _OnboardingFlowScreenState();
}

class _OnboardingFlowScreenState extends State<OnboardingFlowScreen> {
  late final OnboardingService _service;

  @override
  void initState() {
    super.initState();
    _service = OnboardingService(widget.state);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _service,
      builder: (context, _) {
        final state = _service.state;
        switch (state.step) {
          case OnboardingStep.welcome:
            return OnboardingWelcomeView(service: _service);
          case OnboardingStep.chatFlow:
          case OnboardingStep.completed:
            return OnboardingChatView(
              service: _service,
              appState: widget.state,
            );
        }
      },
    );
  }
}

class OnboardingWelcomeView extends StatelessWidget {
  final OnboardingService service;

  const OnboardingWelcomeView({super.key, required this.service});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - 64, // vertical padding
                ),
                child: IntrinsicHeight(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 16),
                      Icon(
                        Icons.smart_toy_outlined,
                        size: 80,
                        color: colorScheme.primary,
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Welcome to PAIOS',
                        textAlign: TextAlign.center,
                        style: textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        "I'm your Personal AI Operating System.",
                        textAlign: TextAlign.center,
                        style: textTheme.bodyLarge?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 32),
                      Card(
                        elevation: 0,
                        color: colorScheme.surfaceContainerHighest.withOpacity(0.4),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'I help you:',
                                style: textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 12),
                              _buildBulletPoint(context, 'Plan your day'),
                              _buildBulletPoint(context, 'Organize projects'),
                              _buildBulletPoint(context, 'Capture events'),
                              _buildBulletPoint(context, 'Learn effectively'),
                              _buildBulletPoint(context, 'Review your progress'),
                            ],
                          ),
                        ),
                      ),
                      const Spacer(),
                      const SizedBox(height: 24),
                      Text(
                        'Would you like a quick guided setup?',
                        textAlign: TextAlign.center,
                        style: textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: service.startSetup,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: colorScheme.primary,
                          foregroundColor: colorScheme.onPrimary,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text(
                          'Start Setup',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: service.skipOnboarding,
                        style: TextButton.styleFrom(
                          foregroundColor: colorScheme.primary,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        child: const Text('Skip'),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildBulletPoint(BuildContext context, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 18,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

class OnboardingChatView extends StatefulWidget {
  final OnboardingService service;
  final AppState appState;

  const OnboardingChatView({
    super.key,
    required this.service,
    required this.appState,
  });

  @override
  State<OnboardingChatView> createState() => _OnboardingChatViewState();
}

class _OnboardingChatViewState extends State<OnboardingChatView> {
  final ScrollController _scrollController = ScrollController();

  @override
  void didUpdateWidget(covariant OnboardingChatView oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Auto scroll to bottom when history changes
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.service.state;
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('PAIOS Onboarding'),
        leading: widget.service.state.history.isEmpty
            ? null
            : IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: widget.service.restartOnboarding,
              ),
        actions: [
          TextButton(
            onPressed: widget.service.skipOnboarding,
            child: Text(
              'Skip',
              style: TextStyle(color: colorScheme.primary),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: state.history.length,
              itemBuilder: (context, index) {
                final message = state.history[index];
                return _buildChatBubble(message);
              },
            ),
          ),
          _buildInteractiveArea(context, state),
        ],
      ),
    );
  }

  Widget _buildChatBubble(ChatMessage message) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final isUser = message.isUser;
    final isSystem = message.text.startsWith('System:');

    if (isSystem) {
      return Center(
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          decoration: BoxDecoration(
            color: colorScheme.secondaryContainer.withOpacity(0.6),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Text(
            message.text,
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSecondaryContainer,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      );
    }

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        decoration: BoxDecoration(
          color: isUser ? colorScheme.primary : colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 0),
            bottomRight: Radius.circular(isUser ? 0 : 16),
          ),
        ),
        child: Text(
          message.text,
          style: textTheme.bodyLarge?.copyWith(
            color: isUser ? colorScheme.onPrimary : colorScheme.onSurface,
          ),
        ),
      ),
    );
  }

  Widget _buildInteractiveArea(BuildContext context, OnboardingState state) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainer,
        border: Border(
          top: BorderSide(color: colorScheme.outlineVariant, width: 0.5),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (state.isWaitingForAction) ...[
              Text(
                'Required task:',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.primary,
                    ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  if (state.actionRoute != null)
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () => _navigateToShortcut(state.actionRoute!),
                        icon: const Icon(Icons.open_in_new),
                        label: Text(_getRouteLabel(state.actionRoute!)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: colorScheme.secondaryContainer,
                          foregroundColor: colorScheme.onSecondaryContainer,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                      ),
                    ),
                  if (state.actionRoute != null) const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: widget.service.verifyAction,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: colorScheme.primary,
                        foregroundColor: colorScheme.onPrimary,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('Verify & Continue'),
                    ),
                  ),
                ],
              ),
            ] else if (state.options.isNotEmpty) ...[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  for (final option in state.options)
                    ActionChip(
                      label: Text(
                        option,
                        style: TextStyle(color: colorScheme.onPrimaryContainer),
                      ),
                      backgroundColor: colorScheme.primaryContainer,
                      onPressed: () => _handleOptionSelected(option),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 10,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(20),
                      ),
                    ),
                ],
              ),
            ] else
              const SizedBox.shrink(),
          ],
        ),
      ),
    );
  }

  void _handleOptionSelected(String option) {
    if (option == "Continue") {
      widget.service.proceedAfterAction();
    } else if (option == "Finish") {
      widget.service.finishOnboarding();
    } else {
      widget.service.selectGoal(option);
    }
  }

  String _getRouteLabel(String route) {
    switch (route) {
      case "projects":
        return "Go to Projects";
      case "capture":
        return "Go to Capture";
      case "today":
        return "Go to Today";
      default:
        return "Go to Screen";
    }
  }

  void _navigateToShortcut(String route) {
    Widget Function(AppState) builder;
    switch (route) {
      case "projects":
        builder = (s) => ProjectsScreen(state: s);
        break;
      case "capture":
        builder = (s) => InboxScreen(state: s);
        break;
      case "today":
      default:
        builder = (s) => PlanningScreen(state: s);
        break;
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => Scaffold(
          appBar: AppBar(
            title: Text(_getRouteLabel(route)),
          ),
          body: builder(widget.appState),
        ),
      ),
    );
  }
}
