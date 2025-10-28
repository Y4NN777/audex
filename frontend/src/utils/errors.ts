const KNOWN_MESSAGES: Record<string, string> = {
  network: "Connexion perdue — réessayez lorsque vous êtes en ligne.",
  timeout: "Temps de réponse dépassé — réessayez dans un instant.",
  default: "Échec de l'envoi — veuillez réessayer."
};

export function toFriendlyError(message?: string, status?: number): string {
  if (!message) return KNOWN_MESSAGES.default;

  const normalized = message.toLowerCase();
  if (status === 0 || normalized.includes("network")) {
    return KNOWN_MESSAGES.network;
  }
  if (normalized.includes("timeout")) {
    return KNOWN_MESSAGES.timeout;
  }

  return KNOWN_MESSAGES.default;
}
