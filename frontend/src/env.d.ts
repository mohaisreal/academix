/// <reference types="astro/client" />

interface ConfirmActionOptions {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'destructive' | string;
  onConfirm: () => void | Promise<void>;
}

interface Window {
  confirmAction?: (options: ConfirmActionOptions) => void;
}
