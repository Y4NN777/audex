import { useEffect, useRef, useState } from "react";

import { useOnlineStatus } from "../hooks/useOnlineStatus";

type Props = {
  syncing: boolean;
  onBackOnline?: () => void | Promise<void>;
};

export function ConnectionBanner({ onBackOnline, syncing }: Props) {
  const online = useOnlineStatus();
  const [showBackOnline, setShowBackOnline] = useState(false);
  const wasOfflineRef = useRef(false);

  useEffect(() => {
    if (online) {
      let timeout: ReturnType<typeof setTimeout> | undefined;
      if (wasOfflineRef.current) {
        if (syncing) {
          setShowBackOnline(true);
          timeout = setTimeout(() => setShowBackOnline(false), 3000);
        } else {
          setShowBackOnline(false);
        }
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
  }, [online, onBackOnline, syncing]);

  if (!online) {
    return <div className="banner offline">Mode hors-ligne : les lots seront synchronisés plus tard.</div>;
  }

  if (showBackOnline && syncing) {
    return <div className="banner online">Connexion rétablie — synchronisation en cours.</div>;
  }

  return null;
}
