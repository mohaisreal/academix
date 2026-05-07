/**
 * API de toasts de Starwind
 * Un sistema sencillo de notificaciones toast independiente del framework.
 * @example
 * ```ts
 * import { toast } from "@/components/starwind/toast";
 * // Uso sencillo
 * toast("Hola, mundo");
 * toast({ title: "Correcto", description: "Elemento guardado" });
 * // Atajos de variantes
 * toast.success("Guardado correctamente");
 * toast.error("Algo ha ido mal");
 * toast.warning("Revisa los datos introducidos");
 * toast.info("Nueva actualización disponible");
 * toast.loading("Procesando...");
 * // Gestión de promesas
 * toast.promise(saveData(), {
 * loading: "Guardando...",
 * success: "Guardado",
 * error: "No se ha podido guardar",
 * });
 * // Gestión
 * const id = toast("Procesando...");
 * toast.update(id, { title: "Casi terminado" });
 * toast.dismiss(id);
 * toast.dismiss(); // cerrar todos
 * ```
 */
export type Variant = "default" | "success" | "error" | "warning" | "info" | "loading";

export interface ToastOptions {
  id?: string;
  title?: string;
  description?: string;
  variant?: Variant;
  /** Duración en ms. Establecer a 0 para infinito (sin autocierre). */
  duration?: number;
  /** Callback cuando empieza la animación de cierre del toast. */
  onClose?: () => void;
  /** Callback cuando el toast se elimina del DOM. */
  onRemove?: () => void;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface PromiseStateOption {
  title?: string;
  description?: string;
  duration?: number;
}

export type PromiseStateValue<T> =
  | string
  | PromiseStateOption
  | ((data: T) => string | PromiseStateOption);

export interface PromiseOptions<T, E = Error> {
  loading: string | PromiseStateOption;
  success: PromiseStateValue<T>;
  error: PromiseStateValue<E>;
}

interface ToastManager {
  add(options: ToastOptions): string;
  update(id: string, options: Partial<ToastOptions>): void;
  close(id: string): void;
  closeAll(): void;
}

/**
 * Obtiene la instancia del gestor de toasts desde window
 */
function getManager(): ToastManager | null {
  if (typeof window === "undefined") return null;
  return (window as any).__starwind__.toast as ToastManager | null;
}

/**
 * Normaliza una cadena u objeto de opciones a ToastOptions
 */
function normalizeOption<T>(
  value: string | PromiseStateOption | ((data: T) => string | PromiseStateOption),
  data?: T,
): Omit<ToastOptions, "variant"> {
  const resolved = typeof value === "function" ? value(data as T) : value;
  if (typeof resolved === "string") {
    return { title: resolved };
  }
  return resolved;
}

/**
 * Crea una notificación toast
 */
function createToast(
  messageOrOptions: string | ToastOptions,
  extraOptions?: Omit<ToastOptions, "title">,
): string {
  let options: ToastOptions;
  if (typeof messageOrOptions === "string") {
    options = { title: messageOrOptions, ...extraOptions };
  } else {
    options = messageOrOptions;
  }

  const manager = getManager();
  if (manager) {
    return manager.add(options);
  }

  console.warn("Toast: No Toaster found. Add <Toaster /> to your layout.");
  return "";
}

/**
 * Crea un toast con una variante concreta
 */
function createVariantToast(
  variant: Variant,
  message: string,
  options?: Omit<ToastOptions, "variant">,
): string {
  return createToast({ ...options, title: message, variant });
}

/**
 * Toast API interface
 */
interface ToastAPI {
  (message: string, options?: Omit<ToastOptions, "title">): string;
  (options: ToastOptions): string;
  success(message: string, options?: Omit<ToastOptions, "variant">): string;
  error(message: string, options?: Omit<ToastOptions, "variant">): string;
  warning(message: string, options?: Omit<ToastOptions, "variant">): string;
  info(message: string, options?: Omit<ToastOptions, "variant">): string;
  loading(message: string, options?: Omit<ToastOptions, "variant">): string;
  promise<T, E = Error>(promise: Promise<T>, options: PromiseOptions<T, E>): Promise<T>;
  update(id: string, options: Partial<ToastOptions>): void;
  dismiss(id?: string): void;
}

/**
 * Función principal de toast con métodos de variante adjuntos
 */
const toast = createToast as ToastAPI;

toast.success = (message: string, options?: Omit<ToastOptions, "variant">) =>
  createVariantToast("success", message, options);

toast.error = (message: string, options?: Omit<ToastOptions, "variant">) =>
  createVariantToast("error", message, options);

toast.warning = (message: string, options?: Omit<ToastOptions, "variant">) =>
  createVariantToast("warning", message, options);

toast.info = (message: string, options?: Omit<ToastOptions, "variant">) =>
  createVariantToast("info", message, options);

toast.loading = (message: string, options?: Omit<ToastOptions, "variant">) =>
  createVariantToast("loading", message, { ...options, duration: 0 });

toast.promise = async <T, E = Error>(
  promise: Promise<T>,
  options: PromiseOptions<T, E>,
): Promise<T> => {
  const loadingOpts = normalizeOption(options.loading);
  const id = createToast({
    ...loadingOpts,
    variant: "loading",
    duration: 0, // No autocerrar mientras está cargando
  });

  try {
    const data = await promise;
    const successOpts = normalizeOption(options.success, data);
    toast.update(id, { ...successOpts, variant: "success" });
    return data;
  } catch (error) {
    const errorOpts = normalizeOption(options.error, error as E);
    toast.update(id, { ...errorOpts, variant: "error" });
    throw error;
  }
};

toast.update = (id: string, options: Partial<ToastOptions>): void => {
  const manager = getManager();
  if (manager) {
    manager.update(id, options);
  } else {
    console.warn("Toast: No Toaster found. Add <Toaster /> to your layout.");
  }
};

toast.dismiss = (id?: string): void => {
  const manager = getManager();
  if (!manager) {
    // Can't dismiss if manager isn't ready
    return;
  }
  if (id) {
    manager.close(id);
  } else {
    manager.closeAll();
  }
};

export { toast };
