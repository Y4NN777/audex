import { useEffect, useState } from "react";

import { useOnlineStatus } from "../hooks/useOnlineStatus";

type Props = {
  onBackOnline?: () => void | Promise<void>;
};

export function ConnectionBanner({ onBackOnline }: Props) {
  const online = useOnlineStatus();
  const [showBackOnline, setShowBackOnline] = useState(false);

  useEffect(() => {
    if (online) {
      setShowBackOnline(true);
      const timeout = setTimeout(() => setShowBackOnline(false), 3000);
      onBackOnline?.();
      return () => clearTimeout(timeout);
    }
    return undefined;
  }, [online, onBackOnline]);

  if (!online) {
    return <div className="banner offline">Mode hors-ligne : les lots seront synchronisés plus tard.</div>;
  }

  if (showBackOnline) {
    return <div className="banner online">Connexion rétablie — synchronisation en cours.</div>;
  }

  return null;
}
