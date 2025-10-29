import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type ToastVariant = "info" | "success" | "error";

type Toast = {
  id: string;
  message: string;
  variant: ToastVariant;
};

type ToastOptions = {
  duration?: number;
};

type ToastContextValue = {
  pushToast: (message: string, variant?: ToastVariant, options?: ToastOptions) => string;
  dismissToast: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Record<string, number>>({});

  const dismissToast = useCallback((id: string) => {
    setToasts((items) => items.filter((toast) => toast.id !== id));
    if (timers.current[id]) {
      window.clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  const pushToast = useCallback(
    (message: string, variant: ToastVariant = "info", options?: ToastOptions) => {
      const id = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      const toast: Toast = { id, message, variant };
      setToasts((items) => [...items, toast]);

      const duration = options?.duration ?? 3500;
      if (duration > 0) {
        timers.current[id] = window.setTimeout(() => dismissToast(id), duration);
      }

      return id;
    },
    [dismissToast]
  );

  const value = useMemo(
    () => ({
      pushToast,
      dismissToast
    }),
    [pushToast, dismissToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.variant}`}>
            <span>{toast.message}</span>
            <button type="button" onClick={() => dismissToast(toast.id)} aria-label="Fermer la notification">
              X
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
