// Parses what the desktop's pairing QR (or a pasted string) contains.
//
// The desktop encodes a versioned payload (M23):
//   paios://pair?lan=<lan_url>&relay=<relay_url>&account=<account>
// carrying whichever endpoints exist, so the phone can auto-select
// LAN -> Relay -> Offline. A plain "http://host:port" is still accepted
// (a generic scanner, or a user typing the address).

class PairingPayload {
  final String? lanUrl;
  final String? relayUrl;
  final String account;

  const PairingPayload({this.lanUrl, this.relayUrl, this.account = 'default'});

  bool get hasLan => lanUrl != null && lanUrl!.isNotEmpty;
  bool get hasRelay => relayUrl != null && relayUrl!.isNotEmpty;
  bool get isUsable => hasLan || hasRelay;

  /// Best-effort parse. Returns a payload with no endpoints when the
  /// text is unrecognised (the caller shows a friendly "couldn't read").
  static PairingPayload parse(String raw) {
    final text = raw.trim();
    if (text.startsWith('paios://pair')) {
      final query = text.contains('?') ? text.split('?').sublist(1).join('?') : '';
      final params = <String, String>{};
      for (final pair in query.split('&')) {
        if (pair.isEmpty) continue;
        final index = pair.indexOf('=');
        if (index <= 0) continue;
        params[pair.substring(0, index)] = pair.substring(index + 1);
      }
      return PairingPayload(
        lanUrl: _clean(params['lan']),
        relayUrl: _clean(params['relay']),
        account: _clean(params['account']) ?? 'default',
      );
    }
    if (text.startsWith('http://') || text.startsWith('https://')) {
      return PairingPayload(lanUrl: text);
    }
    if (RegExp(r'^[\w.-]+(:\d+)?$').hasMatch(text)) {
      // A bare host[:port] the user typed.
      return PairingPayload(lanUrl: 'http://$text');
    }
    return const PairingPayload();
  }

  static String? _clean(String? value) {
    if (value == null) return null;
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
