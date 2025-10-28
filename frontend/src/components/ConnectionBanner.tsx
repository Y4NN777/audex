import { useEffect, useRef, useState } from "react";

import { useOnlineStatus } from "../hooks/useOnlineStatus";

type Props = {
  onBackOnline?: () => void | Promise<void>;
};

export function ConnectionBanner({ onBackOnline }: Props) {
  const online = useOnlineStatus();
  const [showBackOnline, setShowBackOnline] = useState(false);
  const wasOfflineRef = useRef(false);

  useEffect(() => {
    if (online) {
      let timeout: ReturnType<typeof setTimeout> | undefined;
      if (wasOfflineRef.current) {
        setShowBackOnline(true);
        timeout = setTimeout(() => setShowBackOnline(false), 3000);
        void onBackOnline?.();
      }
      wasOfflineRef.current = false;
      return () => {
        if (timeout) {
          clearTimeout(timeout);
        }
      };
    }
    wasOfflineRef.current = true;
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
