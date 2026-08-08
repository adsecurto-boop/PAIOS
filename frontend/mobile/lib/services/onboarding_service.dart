import 'package:flutter/foundation.dart';
import 'app_state.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  ChatMessage({required this.text, required this.isUser, required this.timestamp});
}

enum OnboardingStep {
  welcome,
  chatFlow,
  completed,
}

class OnboardingState {
  final OnboardingStep step;
  final List<ChatMessage> history;
  final String? selectedGoal;
  final int initialProjectCount;
  final int initialInboxCount;
  final bool isWaitingForAction;
  final String? targetAction;
  final String? actionRoute;
  final List<String> options;

  OnboardingState({
    required this.step,
    required this.history,
    this.selectedGoal,
    this.initialProjectCount = 0,
    this.initialInboxCount = 0,
    this.isWaitingForAction = false,
    this.targetAction,
    this.actionRoute,
    this.options = const [],
  });

  OnboardingState copyWith({
    OnboardingStep? step,
    List<ChatMessage>? history,
    String? selectedGoal,
    int? initialProjectCount,
    int? initialInboxCount,
    bool? isWaitingForAction,
    String? targetAction,
    String? actionRoute,
    List<String>? options,
    bool clearAction = false,
  }) =>
      OnboardingState(
        step: step ?? this.step,
        history: history ?? this.history,
        selectedGoal: selectedGoal ?? this.selectedGoal,
        initialProjectCount: initialProjectCount ?? this.initialProjectCount,
        initialInboxCount: initialInboxCount ?? this.initialInboxCount,
        isWaitingForAction: isWaitingForAction ?? this.isWaitingForAction,
        targetAction: clearAction ? null : (targetAction ?? this.targetAction),
        actionRoute: clearAction ? null : (actionRoute ?? this.actionRoute),
        options: options ?? this.options,
      );
}

class AiResponse {
  final String text;
  final List<String> options;
  final String? targetAction;
  final String? actionRoute;

  AiResponse({
    required this.text,
    this.options = const [],
    this.targetAction,
    this.actionRoute,
  });
}

class OnboardingAiEngine {
  AiResponse getInitialResponse(bool hasExistingProjects) {
    if (hasExistingProjects) {
      return AiResponse(
        text: "I see you already have some projects set up. What would you like to do?",
        options: ["Select Existing Project", "Create New Project"],
      );
    }
    return AiResponse(
      text: "Great. Before we begin, what brings you here?",
      options: ["Study", "Work", "Build Habits", "Personal Growth", "Just Exploring"],
    );
  }

  AiResponse respondToGoal(String goal, {bool isProjectSelection = false}) {
    if (isProjectSelection) {
      return AiResponse(
        text: "Great choice! Now, let's learn how to plan your day. Go to the Today screen and check out the Daily rhythm.",
        actionRoute: "today",
      );
    }
    switch (goal) {
      case "Create New Project":
        return AiResponse(
          text: "Let's create your first Project. Go to the Projects screen, tap '+ New Project', and set it up.",
          targetAction: "createProject",
          actionRoute: "projects",
        );
      case "Study":
        return AiResponse(
          text: "I recommend creating your first Learning Project. Go to the Projects screen, tap '+ New Project', name it, and set its type to Study.",
          targetAction: "createProject",
          actionRoute: "projects",
        );
      case "Work":
        return AiResponse(
          text: "I recommend creating your first Office Project. Go to the Projects screen, tap '+ New Project', and create a Work project.",
          targetAction: "createProject",
          actionRoute: "projects",
        );
      case "Build Habits":
        return AiResponse(
          text: "I recommend creating your first Habit Project. Go to the Projects screen, tap '+ New Project', and create a Habit project.",
          targetAction: "createProject",
          actionRoute: "projects",
        );
      case "Personal Growth":
      case "Just Exploring":
      default:
        return AiResponse(
          text: "I recommend capturing your first thought in the Quick Capture Inbox. Go to the Capture screen and add a task or reminder.",
          targetAction: "createInboxItem",
          actionRoute: "capture",
        );
    }
  }

  AiResponse getNextStepResponse() {
    return AiResponse(
      text: "Now, let's learn how to plan your day. Go to the Today screen and check out the Daily rhythm.",
      actionRoute: "today",
      options: ["Continue"],
    );
  }

  AiResponse getCompletionResponse() {
    return AiResponse(
      text: "Awesome! You are all set to use PAIOS. Tap Finish to begin your journey.",
      options: ["Finish"],
    );
  }

  Future<bool> verifyCompletion(OnboardingState state, AppState appState) async {
    if (state.targetAction == "createProject") {
      try {
        final projects = await appState.client.getProjects();
        return projects.length > state.initialProjectCount;
      } catch (_) {
        return false;
      }
    } else if (state.targetAction == "createInboxItem") {
      try {
        final inbox = await appState.client.getInbox();
        return inbox.length > state.initialInboxCount;
      } catch (_) {
        return false;
      }
    }
    return true;
  }
}

class OnboardingService extends ChangeNotifier {
  final AppState _appState;
  final OnboardingAiEngine _engine = OnboardingAiEngine();

  late OnboardingState state;

  OnboardingService(this._appState) {
    _resetState();
  }

  void _resetState() {
    state = OnboardingState(
      step: OnboardingStep.welcome,
      history: [],
    );
  }

  Future<void> startSetup() async {
    int initialProjects = 0;
    try {
      final projects = await _appState.client.getProjects();
      initialProjects = projects.length;
    } catch (_) {}

    final response = _engine.getInitialResponse(initialProjects > 0);
    state = state.copyWith(
      step: OnboardingStep.chatFlow,
      history: [
        ChatMessage(
          text: response.text,
          isUser: false,
          timestamp: DateTime.now(),
        ),
      ],
      options: response.options,
      isWaitingForAction: false,
    );
    notifyListeners();
  }

  Future<void> selectGoal(String goal) async {
    final updatedHistory = List<ChatMessage>.from(state.history)
      ..add(ChatMessage(
        text: goal,
        isUser: true,
        timestamp: DateTime.now(),
      ));

    state = state.copyWith(
      history: updatedHistory,
      selectedGoal: goal,
      options: [],
    );
    notifyListeners();

    if (goal == "Select Existing Project") {
      try {
        final projects = await _appState.client.getProjects();
        final options = projects.map((p) => p['name'].toString()).take(5).toList();
        if (options.isEmpty) {
          options.add("Create New Project");
        }
        state = state.copyWith(
          history: List<ChatMessage>.from(updatedHistory)
            ..add(ChatMessage(
              text: "Which project would you like to start with?",
              isUser: false,
              timestamp: DateTime.now(),
            )),
          options: options,
        );
        notifyListeners();
        return;
      } catch (_) {}
    }

    bool isProjectSelection = updatedHistory.length >= 2 && 
        updatedHistory[updatedHistory.length - 2].text == "Which project would you like to start with?";

    int initialProjects = 0;
    int initialInbox = 0;
    try {
      final projects = await _appState.client.getProjects();
      initialProjects = projects.length;
    } catch (_) {}
    try {
      final inbox = await _appState.client.getInbox();
      initialInbox = inbox.length;
    } catch (_) {}

    final response = _engine.respondToGoal(goal, isProjectSelection: isProjectSelection);
    updatedHistory.add(ChatMessage(
      text: response.text,
      isUser: false,
      timestamp: DateTime.now(),
    ));

    state = state.copyWith(
      history: updatedHistory,
      initialProjectCount: initialProjects,
      initialInboxCount: initialInbox,
      isWaitingForAction: response.targetAction != null,
      targetAction: response.targetAction,
      actionRoute: response.actionRoute,
      options: response.targetAction == null ? ["Continue"] : [],
    );
    notifyListeners();
  }

  Future<void> verifyAction() async {
    state = state.copyWith(options: []);
    notifyListeners();

    final success = await _engine.verifyCompletion(state, _appState);

    final updatedHistory = List<ChatMessage>.from(state.history);
    if (success) {
      updatedHistory.add(ChatMessage(
        text: "System: Verification successful!",
        isUser: false,
        timestamp: DateTime.now(),
      ));

      final response = _engine.getNextStepResponse();
      updatedHistory.add(ChatMessage(
        text: response.text,
        isUser: false,
        timestamp: DateTime.now(),
      ));

      state = state.copyWith(
        history: updatedHistory,
        isWaitingForAction: false,
        clearAction: true,
        options: response.options,
      );
    } else {
      updatedHistory.add(ChatMessage(
        text: "I couldn't verify the completion of your task. Please make sure you completed the action and tap Verify & Continue to try again.",
        isUser: false,
        timestamp: DateTime.now(),
      ));

      state = state.copyWith(
        history: updatedHistory,
      );
    }
    notifyListeners();
  }

  void proceedAfterAction() {
    final updatedHistory = List<ChatMessage>.from(state.history)
      ..add(ChatMessage(
        text: "Continue",
        isUser: true,
        timestamp: DateTime.now(),
      ));

    state = state.copyWith(
      history: updatedHistory,
      options: [],
    );
    notifyListeners();

    final response = _engine.getCompletionResponse();
    updatedHistory.add(ChatMessage(
      text: response.text,
      isUser: false,
      timestamp: DateTime.now(),
    ));

    state = state.copyWith(
      history: updatedHistory,
      options: response.options,
      actionRoute: null,
    );
    notifyListeners();
  }

  void finishOnboarding() {
    _appState.completeOnboarding();
  }

  void skipOnboarding() {
    _appState.completeOnboarding();
  }

  void restartOnboarding() {
    _resetState();
    _appState.restartOnboarding();
  }
}
